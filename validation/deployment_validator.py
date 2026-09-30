"""
Deployment Plan Validation
==========================

Independent validator: it does NOT reuse the planner's evaluation code. Every
constraint is re-derived from the ORIGINAL contracts and checked against the
deployment descriptors produced by the planner.

Inputs
  ../deployment/output/<app>.json              deployment descriptors (D_deploy)
  ../offloadability/output/<app>.json          anchors, statuses, conditions
  ../resource_estimation/output/<app>.json     demands, communication requirements
  ../deployment/infrastructure.json            nodes, links, application bindings
  ../deployment/sla_policy.json                P_SLA

Outputs
  output/<app>.json                            per-application validation result
  output/joint_validation.json                 shared-infrastructure checks (all applications)
  ../deployment/feedback.json                  violations returned to the planner

Usage (from my-thesis/validation):
  python deployment_validator.py               validate the current plans
  python deployment_validator.py --self-test   inject faults into correct plans and
                                               measure how many the validator detects
"""

import copy
import heapq
import json
import math
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
DEP = ROOT / "deployment"
APPS = ["smart_surveillance", "smart_agriculture_iot", "crop_monitoring"]
RES = ("cpu_cores", "memory_gb", "gpu_memory_gb", "storage_gb")
LABEL = {"cpu_cores": "CPU (cores)", "memory_gb": "memory (GB)",
         "gpu_memory_gb": "GPU memory (GB)", "storage_gb": "storage (GB)"}
TOL = 1e-6

DEFAULT_MODELS = {
    "load_split":  {"writes": "split", "reads": "load_balanced", "cpu": "split", "storage": "full"},
    "mirrored":    {"writes": "all_replicas", "reads": "load_balanced", "cpu": "full", "storage": "full"},
    "partitioned": {"writes": "split", "reads": "load_balanced", "cpu": "split", "storage": "split"},
    "single":      {"writes": "split", "reads": "load_balanced", "cpu": "full", "storage": "full"},
}


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Constraint model re-derived from the contracts (independent of the planner)
# --------------------------------------------------------------------------- #
class Context:
    def __init__(self, infra, policy):
        self.infra, self.policy = infra, policy
        self.pl = policy["planning"]
        self.nodes = {n["id"]: n for n in infra["nodes"]}
        self.sites = {s["id"]: s for s in infra["sites"]}
        self.links = {l["id"]: l for l in infra["links"]}
        self.adj = {}
        for l in infra["links"]:
            self.adj.setdefault(l["a"], []).append((l["b"], l))
            self.adj.setdefault(l["b"], []).append((l["a"], l))
        self._routes = {}

    def route(self, a, b):
        if a == b:
            return []
        key = tuple(sorted((a, b)))
        if key not in self._routes:
            dist, prev, pq = {a: 0.0}, {}, [(0.0, a)]
            while pq:
                d, u = heapq.heappop(pq)
                if d > dist.get(u, math.inf):
                    continue
                for v, l in self.adj.get(u, []):
                    if d + l["latency_ms"] < dist.get(v, math.inf):
                        dist[v], prev[v] = d + l["latency_ms"], (u, l["id"])
                        heapq.heappush(pq, (dist[v], v))
            if b not in dist:
                self._routes[key] = None
            else:
                path, v = [], b
                while v != a:
                    u, lid = prev[v]
                    path.append(lid)
                    v = u
                self._routes[key] = path
        return self._routes[key]

    def proximity(self, a, b, level):
        sa, sb = self.nodes[a]["site"], self.nodes[b]["site"]
        if level == "same_site":
            return sa == sb
        if level == "regional":
            return self.sites[sa]["region"] == self.sites[sb]["region"]
        return True

    def model(self, sem):
        m = dict(DEFAULT_MODELS[sem])
        m.update({k: v for k, v in self.pl.get("replication_models", {}).get(sem, {}).items()})
        return m


class AppSpec:
    """What the upstream contracts REQUIRE for one application."""

    def __init__(self, name, ctx):
        self.name = name
        self.ctx = ctx
        off = load(ROOT / "offloadability" / "output" / f"{name}.json")
        res = load(ROOT / "resource_estimation" / "output" / f"{name}.json")
        self.sla = ctx.policy["applications"].get(name, {})
        bind = ctx.infra["application_bindings"][name]
        self.anchors = bind["anchors"]
        self.original = bind.get("original_host", bind.get("current_host", {}))
        prof = {p["unit_id"]: p for p in res["resource_profiles"]}
        self.units = {}
        for o in off["offloadability_profiles"]:
            self.units[o["unit_id"]] = {"status": o["status"], "anchored_to": o.get("anchored_to"),
                                        "follows": o.get("follows_units") or [],
                                        "conditions": o.get("conditions", []), "profile": prof[o["unit_id"]]}
        self.edges = []
        for e in res["communication_requirements"]:
            lat = e.get("latency_sensitivity")
            self.edges.append({"s": e["source"], "t": e["target"], "bw": float(e.get("bandwidth_mbps") or 0),
                               "boundary": e.get("boundary", "unknown"),
                               "latency": lat.get("level") if isinstance(lat, dict) else lat})

    def conds(self, uid, t):
        return [c for c in self.units[uid]["conditions"] if c.get("type") == t]

    def movable(self, uid):
        return self.units[uid]["status"] in ("offloadable", "conditionally_offloadable")

    def semantics(self, uid):
        pl = self.ctx.pl
        if self.conds(uid, "state_handling") and not pl["allow_stateful_replication"]:
            return "single"
        st = self.units[uid]["profile"].get("storage", {})
        if self.conds(uid, "persistent_storage") or st.get("persistent"):
            m = pl.get("persistent_replication", "mirrored")
            return "single" if m == "disallowed" else m
        return "load_split"

    def demand(self, uid, k, comparable=True):
        p, pl = self.units[uid]["profile"], self.ctx.pl
        m = pl["safety_margins"]
        d = {}
        for r, blk, key in (("cpu_cores", "cpu", "typical_cores"), ("memory_gb", "memory", "typical_gb")):
            b = p.get(blk, {})
            v, pv = b.get(key), b.get("provenance", "assumed")
            if v is None:
                v, pv = (pl["default_unknown_demand"][r], "unknown") if comparable else (0.0, pv)
            d[r] = float(v) * m.get(pv, m["assumed"])
        g = p.get("gpu", {})
        d["gpu_memory_gb"] = float(g.get("memory_gb") or 0) if g.get("requirement") == "required" else 0.0
        d["storage_gb"] = float(p.get("storage", {}).get("size_gb") or 0)
        if self.units[uid]["status"] == "follows_supported_units":
            return {r: (d[r] if r == "storage_gb" else 0.0) for r in RES}
        if k > 1 and self.movable(uid):
            mdl = self.ctx.model(self.semantics(uid))
            if mdl["cpu"] == "split":
                d["cpu_cores"] = d["cpu_cores"] / k + pl.get("per_replica_overhead", {}).get("cpu_cores", 0)
            if mdl["storage"] == "split":
                d["storage_gb"] /= k
        return d


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
class Report:
    def __init__(self):
        self.checks = []

    def add(self, cid, name, ok, detail, severity="error", unit=None, node=None):
        self.checks.append({"id": cid, "constraint": name,
                            "result": "pass" if ok else ("fail" if severity == "error" else "warning"),
                            "detail": detail, "unit": unit, "node": node})

    @property
    def errors(self):
        return [c for c in self.checks if c["result"] == "fail"]

    @property
    def warnings(self):
        return [c for c in self.checks if c["result"] == "warning"]


def placement_of(desc):
    return {p["unit_id"]: [r["node"] for r in p["replicas"]] for p in desc.get("placements", [])}


def app_loads(spec, pl_map, ctx):
    """Per-node resource reservation and per-link traffic of one application."""
    node_load = {n: {r: 0.0 for r in RES} for n in ctx.nodes}
    hosting = set()
    for uid, nodes in pl_map.items():
        for n in nodes:
            comp = ctx.nodes[n]["comparable"]
            if not comp:
                continue
            d = spec.demand(uid, len(nodes), comp)
            for r in RES:
                node_load[n][r] += d[r]
            hosting.add(n)
    for n in hosting:
        for r, v in ctx.pl["runtime_overhead_per_node"].items():
            node_load[n][r] += v
    link_load = {l: 0.0 for l in ctx.links}
    unrouted = []
    for e in spec.edges:
        S, T = pl_map.get(e["s"], []), pl_map.get(e["t"], [])
        if not S or not T or e["boundary"] == "hardware":
            continue
        sm = ctx.model(spec.semantics(e["s"])) if spec.movable(e["s"]) else None
        tm = ctx.model(spec.semantics(e["t"])) if spec.movable(e["t"]) else None
        if sm and sm["reads"] == "primary":
            S = S[:1]
        tdiv = 1 if (tm and tm["writes"] == "all_replicas" and len(T) > 1) else len(T)
        share = e["bw"] / (len(S) * tdiv)
        for a in S:
            for b in T:
                if a == b:
                    continue
                path = ctx.route(a, b)
                if path is None:
                    unrouted.append(f"{e['s']}->{e['t']} ({a} to {b})")
                    continue
                for lid in path:
                    link_load[lid] += share
    return node_load, link_load, unrouted


def validate_app(spec, desc, ctx):
    rep = Report()
    pl_map = placement_of(desc)
    target = spec.sla.get("availability_target", 0)
    mode = ctx.pl.get("availability_mode", "soft")

    if desc.get("status") not in ("feasible",):
        rep.add("V0", "planner produced a plan", False, f"descriptor status = {desc.get('status')}")
        return rep, pl_map

    # V1 completeness
    for uid in spec.units:
        nodes = pl_map.get(uid, [])
        rep.add("V1", "every unit is deployed on known nodes",
                bool(nodes) and all(n in ctx.nodes for n in nodes),
                f"{uid} -> {nodes}" if nodes else f"{uid} is not deployed", unit=uid)
    extra = set(pl_map) - set(spec.units)
    if extra:
        rep.add("V1", "every unit is deployed on known nodes", False, f"unknown units in descriptor: {sorted(extra)}")

    for uid, u in spec.units.items():
        nodes = [n for n in pl_map.get(uid, []) if n in ctx.nodes]
        st = u["status"]
        # V2 anchoring
        if st == "non_offloadable":
            anchor_node = spec.anchors.get(u["anchored_to"])
            rep.add("V2", "non-offloadable units stay on their anchor", nodes == [anchor_node],
                    f"{uid} must run only on {anchor_node} (anchor {u['anchored_to']}), found {nodes}",
                    unit=uid, node=",".join(nodes))
        # V3 follower co-location
        if st == "follows_supported_units":
            need = sorted({n for s in u["follows"] for n in pl_map.get(s, [])})
            rep.add("V3", "initialization units are co-located with the units they support",
                    sorted(set(nodes)) == need,
                    f"{uid} must be on {need} (hosts of {', '.join(u['follows'])}), found {sorted(set(nodes))}",
                    unit=uid)
        if spec.movable(uid):
            # V4 host eligibility
            for n in nodes:
                nd = ctx.nodes[n]
                ok = nd["comparable"] and (nd["tier"] != "device" or n == spec.original.get(uid))
                rep.add("V4", "offloaded units run on eligible hosts", ok,
                        f"{uid} on {n}: " + ("eligible" if ok else "non-comparable device" if not nd["comparable"]
                                             else "local device of another user/application"), unit=uid, node=n)
            # V5 unit-level conditions
            for c in spec.conds(uid, "gpu_required"):
                for n in nodes:
                    ok = (ctx.nodes[n]["capacity"].get("gpu_memory_gb") or 0) + TOL >= float(c.get("value") or 0)
                    rep.add("V5", "GPU requirement", ok, f"{uid} needs {c.get('value')} GB GPU memory; "
                            f"{n} has {ctx.nodes[n]['capacity'].get('gpu_memory_gb') or 0} GB", unit=uid, node=n)
            for c in spec.conds(uid, "external_service_access"):
                for n in nodes:
                    rep.add("V5", "external service access", bool(ctx.nodes[n]["internet_access"]),
                            f"{uid} needs Internet access on {n}", unit=uid, node=n)
            for c in spec.conds(uid, "network_proximity"):
                peer, lvl = c.get("related_unit"), c.get("unit") or c.get("value")
                for a in nodes:
                    for b in pl_map.get(peer, []):
                        rep.add("V6", "proximity condition", ctx.proximity(a, b, lvl),
                                f"{uid} on {a} must be {lvl} with {peer} on {b}", unit=uid, node=a)
            # V7 replication rules
            sem = spec.semantics(uid)
            rule = spec.sla.get("units", {}).get(uid, {})
            desired, mx = int(rule.get("desired_replicas", 1)), int(rule.get("max_replicas", rule.get("desired_replicas", 1)))
            k = len(nodes)
            rep.add("V7", "one replica per node (anti-affinity)", len(set(nodes)) == k,
                    f"{uid} replicas {nodes}", unit=uid)
            rep.add("V7", "replica count within SLA maximum", k <= max(mx, 1),
                    f"{uid}: {k} replicas, max {mx}", unit=uid)
            if sem == "single":
                rep.add("V7", "stateful units are not replicated", k == 1,
                        f"{uid} is stateful/single ({k} replicas)", unit=uid)
            elif ctx.pl.get("replication_policy", "sla_required") == "sla_required":
                rep.add("V7", "SLA-required replicas are deployed", k >= min(desired, mx),
                        f"{uid}: {k} of {min(desired, mx)} requested replicas", unit=uid)
            # V8 availability (anchored units excluded by definition)
            a = 1 - math.prod(1 - ctx.nodes[n]["availability"] for n in set(nodes)) if nodes else 0
            rep.add("V8", "availability target (movable units)", a + TOL >= target,
                    f"{uid}: availability {a:.4f}, target {target} ({mode} constraint)",
                    severity="error" if mode == "hard" else "warning", unit=uid)
            # V9 open assumptions on offloaded units
            open_a = spec.conds(uid, "verify_assumption")
            if open_a and any(n != spec.original.get(uid) for n in nodes):
                strict = ctx.pl.get("strict_assumptions", False)
                rep.add("V9", "offloaded units have no unverified assumptions", False,
                        f"{uid} is offloaded while {len(open_a)} assumption(s) remain to verify",
                        severity="error" if strict else "warning", unit=uid)

    # V10 hardware edges not split
    for e in spec.edges:
        if e["boundary"] == "hardware":
            S, T = set(pl_map.get(e["s"], [])), set(pl_map.get(e["t"], []))
            rep.add("V10", "hardware edges are not split across nodes", S == T,
                    f"{e['s']}->{e['t']} on {sorted(S)} / {sorted(T)}")

    # V11 consistency with the descriptor (cross-check of the planner's reported link loads)
    _, link_load, unrouted = app_loads(spec, pl_map, ctx)
    for u in unrouted:
        rep.add("V12", "every flow has a network path", False, f"no path for {u}")
    reported = desc.get("link_load_mbps", {})
    for lid in set(reported) | {l for l, v in link_load.items() if v > 0}:
        a, b = link_load.get(lid, 0.0), float(reported.get(lid, 0.0))
        ok = abs(a - b) <= max(1e-5, 1e-3 * max(a, b))
        rep.add("V11", "reported link load matches recomputation", ok,
                f"{lid}: descriptor {b:.6g} Mbps, recomputed {a:.6g} Mbps", severity="warning")
    return rep, pl_map


def validate_joint(specs, maps, ctx):
    """Capacity of shared nodes and links with ALL applications deployed together."""
    rep = Report()
    ut = ctx.pl["utilization_target"]
    total_n = {n: {r: 0.0 for r in RES} for n in ctx.nodes}
    total_l = {l: 0.0 for l in ctx.links}
    by_node = {n: {r: [] for r in RES} for n in ctx.nodes}
    for name, spec in specs.items():
        nl, ll, _ = app_loads(spec, maps[name], ctx)
        for n in nl:
            for r in RES:
                if nl[n][r] > TOL:
                    total_n[n][r] += nl[n][r]
                    by_node[n][r].append(f"{name} {nl[n][r]:.3g}")
        for l in ll:
            total_l[l] += ll[l]
    for n, loads in total_n.items():
        for r, v in loads.items():
            if v <= TOL:
                continue
            cap = ctx.nodes[n]["capacity"].get(r) or 0
            rep.add("J1", "node capacity within utilization target (all applications)", v <= ut * cap + TOL,
                    f"{n} {LABEL[r]}: {v:.3g} of {cap} (limit {ut:.0%}) from {', '.join(by_node[n][r])}", node=n)
    for l, v in total_l.items():
        if v <= 0:
            continue
        cap = ctx.links[l]["bandwidth_mbps"]
        rep.add("J2", "link bandwidth within utilization target (all applications)", v <= ut * cap + TOL,
                f"{l}: {v:.6g} Mbps of {cap} Mbps (limit {ut:.0%})")
    # start-up peaks of initialization units against the final free capacity
    for name, spec in specs.items():
        for uid, u in spec.units.items():
            if u["status"] != "follows_supported_units":
                continue
            p = u["profile"]
            for n in maps[name].get(uid, []):
                for r, blk, key in (("cpu_cores", "cpu", "peak_cores"), ("memory_gb", "memory", "peak_gb")):
                    pk = p.get(blk, {}).get(key)
                    if pk is None:
                        continue
                    free = (ctx.nodes[n]["capacity"].get(r) or 0) - total_n[n][r]
                    rep.add("J3", "start-up peak of initialization units fits", pk <= free + TOL,
                            f"{name}/{uid} needs {pk} {LABEL[r]} at start-up on {n}; {free:.3g} free", node=n)
    return rep, total_n, total_l


# --------------------------------------------------------------------------- #
# Running
# --------------------------------------------------------------------------- #
def summarize(rep):
    return {"valid": not rep.errors, "checks": len(rep.checks),
            "passed": sum(c["result"] == "pass" for c in rep.checks),
            "errors": len(rep.errors), "warnings": len(rep.warnings)}


def run(descs, ctx, specs):
    results, maps = {}, {}
    for name, d in descs.items():
        rep, maps[name] = validate_app(specs[name], d, ctx)
        results[name] = rep
    jrep, tn, tl = validate_joint(specs, maps, ctx)
    return results, jrep, tn, tl


def main():
    ctx = Context(load(DEP / "infrastructure.json"), load(DEP / "sla_policy.json"))
    apps = [a for a in APPS if (DEP / "output" / f"{a}.json").exists()]
    specs = {a: AppSpec(a, ctx) for a in apps}
    descs = {a: load(DEP / "output" / f"{a}.json") for a in apps}
    if "--self-test" in sys.argv:
        return self_test(ctx, specs, descs)

    results, jrep, tn, tl = run(descs, ctx, specs)
    out = BASE / "output"
    out.mkdir(exist_ok=True)
    feedback = {"exclude_nodes": {}, "notes": []}
    for name, rep in results.items():
        s = summarize(rep)
        joint_err = [c for c in jrep.errors if name in c["detail"]]
        s["valid"] = s["valid"] and not joint_err
        res = {"application_id": name, "result": "Valid" if s["valid"] else "Invalid", "summary": s,
               "violations": rep.errors + joint_err, "warnings": rep.warnings, "checks": rep.checks}
        with open(out / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        for c in rep.errors:
            if c["unit"] and c["node"]:
                for n in str(c["node"]).split(","):
                    feedback["exclude_nodes"].setdefault(name, {}).setdefault(c["unit"], [])
                    if n and n not in feedback["exclude_nodes"][name][c["unit"]]:
                        feedback["exclude_nodes"][name][c["unit"]].append(n)
            feedback["notes"].append(f"{name}: {c['constraint']}: {c['detail']}")
        print(f"\n=== {name}: {res['result']}  ({s['passed']}/{s['checks']} checks passed, "
              f"{s['errors']} errors, {s['warnings']} warnings)")
        for c in rep.errors:
            print(f"  ERROR   [{c['id']}] {c['detail']}")
        for c in rep.warnings:
            if c["id"] != "V11":
                print(f"  warning [{c['id']}] {c['detail']}")
    js = summarize(jrep)
    with open(out / "joint_validation.json", "w", encoding="utf-8") as f:
        json.dump({"result": "Valid" if js["valid"] else "Invalid", "summary": js,
                   "violations": jrep.errors, "checks": jrep.checks,
                   "node_usage": {n: {r: round(v, 4) for r, v in u.items() if v > 0} for n, u in tn.items()
                                  if any(v > 0 for v in u.values())},
                   "link_usage_mbps": {l: round(v, 6) for l, v in tl.items() if v > 0}}, f, indent=2)
    for c in jrep.errors:
        feedback["notes"].append(f"shared infrastructure: {c['detail']}")
    print(f"\n=== shared infrastructure: {'Valid' if js['valid'] else 'Invalid'}  "
          f"({js['passed']}/{js['checks']} checks passed)")
    for c in jrep.errors:
        print(f"  ERROR   [{c['id']}] {c['detail']}")
    fb = DEP / "feedback.json"
    if feedback["exclude_nodes"] or feedback["notes"]:
        with open(fb, "w", encoding="utf-8") as f:
            json.dump(feedback, f, indent=2)
        print(f"\nViolations returned to the planner in {fb} - re-run the planner to reconsider them.")
    elif fb.exists():
        fb.unlink()
    print(f"Validation results written to {out}")


# --------------------------------------------------------------------------- #
# Fault injection: does the validator catch wrong plans?
# --------------------------------------------------------------------------- #
def _set(desc, uid, nodes):
    for p in desc["placements"]:
        if p["unit_id"] == uid:
            p["replicas"] = [{"node": n} for n in nodes]


def self_test(ctx, specs, descs):
    ss, cm = "smart_surveillance", "crop_monitoring"
    faults = [
        (ss, "anchored camera unit U2 moved to an Edge node", lambda d: _set(d, "U2", ["edge_1"]), "V2"),
        (ss, "GPU unit U5 placed on a node without GPU", lambda d: _set(d, "U5", ["edge_2"]), "V5"),
        (ss, "U3 moved to the metro site (far from the camera)", lambda d: _set(d, "U3", ["edge_7"]), "V6"),
        (ss, "model loader U4 not co-located with U6", lambda d: _set(d, "U6", ["edge_3"]), "V3"),
        (ss, "both U7 replicas on the same node", lambda d: _set(d, "U7", ["edge_2", "edge_2"]), "V7"),
        (ss, "stateful tracking unit U5 replicated", lambda d: _set(d, "U5", ["edge_1", "edge_3"]), "V7"),
        (ss, "U3 placed on another user's phone", lambda d: _set(d, "U3", ["agri_phone"]), "V4"),
        (ss, "U3 offloaded: camera feed overloads the operator PC link", lambda d: _set(d, "U3", ["edge_2"]), "J2"),
        (ss, "a unit missing from the plan", lambda d: d["placements"].pop(), "V1"),
        (cm, "SLA-required replica of storage U4 removed", lambda d: _set(d, "U4", ["edge_4"]), "V7"),
        (cm, "crop processing placed on a microcontroller", lambda d: _set(d, "U2", ["crop_sensor"]), "V4"),
    ]
    base_res, base_joint, _, _ = run(descs, ctx, specs)
    baseline_ok = all(not r.errors for r in base_res.values()) and not base_joint.errors
    print(f"Baseline plans valid: {baseline_ok}\n")
    detected, rows = 0, []
    for app, name, mutate, expected in faults:
        d2 = copy.deepcopy(descs)
        mutate(d2[app])
        res, jrep, _, _ = run(d2, ctx, specs)
        errs = res[app].errors + jrep.errors
        ids = sorted({c["id"] for c in errs})
        hit = bool(errs)
        detected += hit
        rows.append({"application": app, "fault": name, "expected_check": expected,
                     "detected": hit, "raised_checks": ids,
                     "first_violation": errs[0]["detail"] if errs else None})
        print(f"  {'DETECTED' if hit else 'MISSED  '}  {name:<58} expected {expected:<4} raised {ids}")
    rate = detected / len(faults)
    print(f"\nDetection rate: {detected}/{len(faults)} = {rate:.0%}")
    out = BASE / "output"
    out.mkdir(exist_ok=True)
    with open(out / "self_test.json", "w", encoding="utf-8") as f:
        json.dump({"baseline_valid": baseline_ok, "detection_rate": rate, "faults": rows}, f, indent=2)


if __name__ == "__main__":
    main()
