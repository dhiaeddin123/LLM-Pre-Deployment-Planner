"""
Deployment Planner
==================

Deterministic (no LLM) planner. It consumes the contracts produced by the
previous stages and computes a deployment plan on a shared infrastructure.

Inputs
  ../resource_estimation/output/<app>.json   resource profiles + communication requirements
  ../offloadability/output/<app>.json        anchors, statuses, conditions
  infrastructure.json                        nodes, sites, links, application bindings
  sla_policy.json                            planning rules, objective weights, per-app SLA

Algorithm (per application, applications planned by priority on the residual infrastructure)
  1. Fix anchored units on their anchor node.
  2. GenerateCandidates: for each movable unit, the nodes that satisfy its unit-level
     conditions (GPU, storage, external access, proximity to anchored peers, strict assumptions).
  3. For every combination (exhaustive, or greedy + local search when too many):
       SatisfiesResources      node CPU / memory / GPU / storage with utilization target and
                               provenance-based safety margins
       SatisfiesOffloadability anchors, hardware edges, proximity, link bandwidth on every path
       Evaluate                weighted objective (traffic, WAN traffic, latency, device load,
                               load imbalance, cloud usage, assumption risk, availability)
  4. SelectFeasibleConfiguration: best score; then replication per SLA, load distribution,
     co-location of 'follows_supported_units' units.
  5. Baselines for comparison: all_local, cloud_only, greedy_first_fit.

Usage (from my-thesis/deployment):
  python deployment_planner.py                    # all applications, joint plan
  python deployment_planner.py smart_surveillance # one application
"""

import heapq
import itertools
import json
import math
import statistics
import sys
from copy import deepcopy
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
APPS = ["smart_surveillance", "smart_agriculture_iot", "crop_monitoring"]
RES = ("cpu_cores", "memory_gb", "gpu_memory_gb", "storage_gb")
EPS = 1e-12
RES_LABEL = {"cpu_cores": ("CPU", "cores"), "memory_gb": ("memory", "GB"),
             "gpu_memory_gb": ("GPU memory", "GB"), "storage_gb": ("storage", "GB")}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class Infrastructure:
    def __init__(self, data):
        self.data = data
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.sites = {s["id"]: s for s in data["sites"]}
        self.links = {l["id"]: l for l in data["links"]}
        self.bindings = data["application_bindings"]
        self.adj = {}
        for l in data["links"]:
            self.adj.setdefault(l["a"], []).append((l["b"], l))
            self.adj.setdefault(l["b"], []).append((l["a"], l))
        self._paths = {}
        # residual capacity (reduced as applications are planned)
        self.used = {n: {r: 0.0 for r in RES} for n in self.nodes}
        self.link_used = {l: 0.0 for l in self.links}

    def path(self, a, b):
        """Lowest-latency path between two vertices: (latency_ms, [link ids])."""
        if a == b:
            return 0.0, []
        key = (a, b) if a < b else (b, a)
        if key in self._paths:
            return self._paths[key]
        dist, prev, pq = {a: 0.0}, {}, [(0.0, a)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == b:
                break
            if d > dist.get(u, math.inf):
                continue
            for v, l in self.adj.get(u, []):
                nd = d + l["latency_ms"]
                if nd < dist.get(v, math.inf):
                    dist[v], prev[v] = nd, (u, l["id"])
                    heapq.heappush(pq, (nd, v))
        if b not in dist:
            res = (math.inf, None)
        else:
            links, v = [], b
            while v != a:
                u, lid = prev[v]
                links.append(lid)
                v = u
            res = (dist[b], links[::-1])
        self._paths[key] = res
        return res

    def site(self, n):
        return self.nodes[n]["site"]

    def region(self, n):
        return self.sites[self.site(n)]["region"]

    def proximity_ok(self, n1, n2, level):
        if level == "same_site":
            return self.site(n1) == self.site(n2)
        if level == "regional":
            return self.region(n1) == self.region(n2)
        return True

    def capacity(self, n, r):
        return self.nodes[n]["capacity"].get(r)


class Application:
    """Merges the resource estimation and offloadability outputs of one app."""

    def __init__(self, name, infra, policy, resource_document=None, offloadability_document=None):
        self.name = name
        self.res = resource_document or load_json(ROOT / "resource_estimation" / "output" / f"{name}.json")
        self.off = offloadability_document or load_json(ROOT / "offloadability" / "output" / f"{name}.json")
        self.bind = infra.bindings[name]
        self.sla = policy["applications"].get(name, {})
        self.planning = policy["planning"]
        rp = {p["unit_id"]: p for p in self.res["resource_profiles"]}
        self.units = {}
        for o in self.off["offloadability_profiles"]:
            uid = o["unit_id"]
            p = rp[uid]
            self.units[uid] = {
                "id": uid, "name": o.get("name", p.get("name")), "status": o["status"],
                "anchored_to": o.get("anchored_to"), "follows": o.get("follows_units") or [],
                "conditions": o.get("conditions", []), "profile": p,
                "blocking_factors": o.get("blocking_factors", []),
                # node on which the unit runs BEFORE planning (not where it is deployed)
                "original_host": self.bind.get("original_host", self.bind.get("current_host", {})).get(uid),
            }
        self.edges = []
        for e in self.res["communication_requirements"]:
            lat = e.get("latency_sensitivity")
            lat = lat.get("level") if isinstance(lat, dict) else (lat or "unknown")
            self.edges.append({"s": e["source"], "t": e["target"], "bw": float(e.get("bandwidth_mbps") or 0.0),
                               "boundary": e.get("boundary", "unknown"), "latency": lat})
        self.fixed = {u: infra.bindings[name]["anchors"][x["anchored_to"]]
                      for u, x in self.units.items() if x["status"] == "non_offloadable"}
        self.followers = [u for u, x in self.units.items() if x["status"] == "follows_supported_units"]
        self.movable = [u for u, x in self.units.items() if u not in self.fixed and u not in self.followers]

    # --- demand of one instance, with provenance safety margin ---------------
    def demand(self, uid, node_comparable=True):
        p = self.units[uid]["profile"]
        m = self.planning["safety_margins"]
        dflt = self.planning["default_unknown_demand"]
        d = {}
        for r, block, key in (("cpu_cores", "cpu", "typical_cores"), ("memory_gb", "memory", "typical_gb")):
            b = p.get(block, {})
            v, prov = b.get(key), b.get("provenance", "assumed")
            if v is None:
                v, prov = (dflt[r], "unknown") if node_comparable else (0.0, prov)
            d[r] = float(v) * m.get(prov, m["assumed"])
        g = p.get("gpu", {})
        d["gpu_memory_gb"] = float(g.get("memory_gb") or 0.0) if g.get("requirement") == "required" else 0.0
        s = p.get("storage", {})
        d["storage_gb"] = float(s.get("size_gb") or 0.0)
        return d

    def peak(self, uid):
        p = self.units[uid]["profile"]
        return {"cpu_cores": p.get("cpu", {}).get("peak_cores"), "memory_gb": p.get("memory", {}).get("peak_gb")}

    def conds(self, uid, ctype):
        return [c for c in self.units[uid]["conditions"] if c.get("type") == ctype]

    def is_stateful(self, uid):
        return bool(self.conds(uid, "state_handling"))

    def is_persistent(self, uid):
        st = self.units[uid]["profile"].get("storage", {})
        return bool(self.conds(uid, "persistent_storage")) or bool(st.get("persistent"))

    def replication_semantics(self, uid, policy):
        """How replicas of a unit share its work (made explicit, see paper section):
        load_split  : stateless work, requests/traffic and CPU divided among replicas
        mirrored    : persistent store, every replica receives ALL writes and keeps a full copy
        partitioned : persistent store sharded, each replica stores 1/k of the data
        single      : not replicable (stateful unit, or persistent replication disallowed)"""
        pl = policy["planning"]
        if self.is_stateful(uid) and not pl["allow_stateful_replication"]:
            return "single"
        if self.is_persistent(uid):
            mode = pl.get("persistent_replication", "mirrored")
            return "single" if mode == "disallowed" else mode
        return "load_split"


# --------------------------------------------------------------------------- #
# Candidate generation
# --------------------------------------------------------------------------- #
def generate_candidates(app, infra):
    strict = app.planning["strict_assumptions"]
    cands, reasons = {}, {}
    # violations returned by the validation stage (deployment/feedback.json)
    fb_path = BASE / "feedback.json"
    excluded = load_json(fb_path).get("exclude_nodes", {}).get(app.name, {}) if fb_path.exists() else {}
    for uid in app.movable:
        u, ok, rej = app.units[uid], [], {}
        for nid, n in infra.nodes.items():
            why = None
            d = app.demand(uid)
            if not n["comparable"]:
                why = "non-comparable device (microcontroller)"
            elif n["tier"] == "device" and nid != u["original_host"]:
                why = "foreign local device"
            elif d["gpu_memory_gb"] > (n["capacity"]["gpu_memory_gb"] or 0):
                why = "no GPU / insufficient GPU memory"
            elif app.conds(uid, "external_service_access") and not n["internet_access"]:
                why = "no internet access"
            elif strict and app.conds(uid, "verify_assumption") and u["original_host"] and nid != u["original_host"]:
                why = "strict_assumptions: unit with unverified assumption stays on its current host"
            else:
                for c in app.conds(uid, "network_proximity"):
                    peer = c.get("related_unit")
                    if peer in app.fixed and not infra.proximity_ok(nid, app.fixed[peer], c.get("unit") or c.get("value")):
                        why = f"proximity {c.get('unit')} to {peer} ({app.fixed[peer]}) violated"
                        break
            if not why and nid in excluded.get(uid, []):
                why = "excluded by validation feedback (deployment/feedback.json)"
            if why:
                rej[nid] = why
            else:
                ok.append(nid)
        cands[uid], reasons[uid] = ok, rej
    return cands, reasons


# --------------------------------------------------------------------------- #
# Evaluation of one configuration
# --------------------------------------------------------------------------- #
def evaluate(app, infra, placement, policy, final=False):
    """placement: {uid: [node, ...]} for ALL units (fixed, movable with replicas, followers).
    Returns (feasible, score, details)."""
    pl = policy["planning"]
    ut = pl["utilization_target"]
    obj = policy["objective"]
    violations, checks = [], []

    # ---- node loads ---------------------------------------------------------
    load = {n: {r: 0.0 for r in RES} for n in infra.nodes}
    contrib = {n: {r: [] for r in RES} for n in infra.nodes}
    app_nodes = set()
    for uid, nodes in placement.items():
        is_follower = uid in app.followers
        for nid in nodes:
            comparable = infra.nodes[nid]["comparable"]
            d = app.demand(uid, comparable)
            k = len(nodes)
            model = (replication_model(policy, app.replication_semantics(uid, policy))
                     if k > 1 and uid in app.movable else None)
            if model and model["cpu"] == "split":
                # each replica processes 1/k of the work plus a fixed per-replica overhead;
                # memory and GPU memory stay per replica (each loads its own model and state)
                d["cpu_cores"] = d["cpu_cores"] / k + pl.get("per_replica_overhead", {}).get("cpu_cores", 0.0)
            if model and model["storage"] == "split":
                d["storage_gb"] = d["storage_gb"] / k  # each shard holds 1/k of the data
            if is_follower:  # transient: only persistent storage is reserved
                d = {r: (d[r] if r == "storage_gb" else 0.0) for r in RES}
            if not comparable:
                continue
            for r in RES:
                load[nid][r] += d[r]
                if d[r] > EPS:
                    contrib[nid][r].append(f"{uid} ({d[r]:.3g} {RES_LABEL[r][1]})")
            app_nodes.add(nid)
    for nid in app_nodes:  # one runtime per node hosting the application
        for r, v in pl["runtime_overhead_per_node"].items():
            load[nid][r] += v

    util = {}
    for nid in app_nodes:
        util[nid] = {}
        for r in RES:
            cap = infra.capacity(nid, r) or 0.0
            total = infra.used[nid][r] + load[nid][r]
            if load[nid][r] <= EPS:
                continue
            u = total / cap if cap > 0 else math.inf
            util[nid][r] = u
            if u > ut + EPS:
                label, unit_ = RES_LABEL[r]
                who = ", ".join(contrib[nid][r]) or "runtime overhead"
                if cap <= 0:
                    violations.append(f"{nid} has no {label} (capacity 0 {unit_}), but "
                                      f"{who} {'requires' if len(contrib[nid][r]) == 1 else 'require'} it")
                else:
                    violations.append(f"{nid}: {label} demand {total:.3g} {unit_} from {who} exceeds "
                                      f"{ut:.0%} of its capacity ({cap} {unit_})")

    # ---- follower startup peak check ---------------------------------------
    for f in app.followers:
        pk = app.peak(f)
        for nid in placement.get(f, []):
            for r in ("cpu_cores", "memory_gb"):
                if pk[r] is None:
                    continue
                free = (infra.capacity(nid, r) or 0) - infra.used[nid][r] - load[nid][r]
                if pk[r] > free + EPS:
                    violations.append(f"{f} (initialization) needs {pk[r]} {RES_LABEL[r][1]} of {RES_LABEL[r][0]} "
                                      f"at start-up on {nid}, but only {free:.3g} {RES_LABEL[r][1]} are free")

    # ---- communication -------------------------------------------------------
    link_load = {l: 0.0 for l in infra.links}
    link_flows = {l: {} for l in infra.links}
    total_traffic = wan = lat_cost = 0.0
    for e in app.edges:
        S, T = placement.get(e["s"], []), placement.get(e["t"], [])
        if not S or not T:
            continue
        if e["boundary"] == "hardware" and set(S) != set(T):
            violations.append(f"hardware edge {e['s']}->{e['t']} split across {S} / {T}")
            continue
        # load_split / partitioned target: the flow is divided among target replicas;
        # mirrored target: every replica receives the full flow (each write is copied).
        # Flow INTO a replicated unit = writes; flow OUT of it = reads/results.
        #   writes = all_replicas : every target replica receives the full flow (mirroring)
        #   writes = split        : the flow is divided among target replicas
        #   reads  = load_balanced: source replicas share the outgoing flow
        #   reads  = primary      : only the first (primary) source replica emits it
        t_model = replication_model(policy, app.replication_semantics(e["t"], policy)) if e["t"] in app.movable else None
        s_model = replication_model(policy, app.replication_semantics(e["s"], policy)) if e["s"] in app.movable else None
        if s_model and s_model["reads"] == "primary":
            S = S[:1]
        t_div = 1 if (t_model and t_model["writes"] == "all_replicas") else len(T)
        share = e["bw"] / (len(S) * t_div)
        worst = 0.0
        for a, b in itertools.product(S, T):
            if a == b:
                continue
            latency, links = infra.path(a, b)
            if links is None:
                violations.append(f"no network path between {a} and {b} for {e['s']}->{e['t']}")
                continue
            total_traffic += share
            for lid in links:
                link_load[lid] += share
                key = f"{e['s']}->{e['t']}"
                link_flows[lid][key] = link_flows[lid].get(key, 0.0) + share
                if infra.links[lid]["type"] == "wan":
                    wan += share
            worst = max(worst, latency)
        lat_cost += obj["latency_weights"].get(e["latency"], 0.3) * worst
    for lid, v in link_load.items():
        if v <= 0:
            continue
        cap = infra.links[lid]["bandwidth_mbps"]
        tot = infra.link_used[lid] + v
        if tot > ut * cap + EPS:
            L = infra.links[lid]
            flows = ", ".join(f"{k} {v:.4g}" for k, v in sorted(link_flows[lid].items(), key=lambda x: -x[1]))
            violations.append(f"link {lid} ({L['a']} - {L['b']}, {L['type']}): {tot:.4g} Mbps exceeds "
                              f"{ut:.0%} of its {cap} Mbps capacity; flows: {flows}")

    # ---- proximity and bandwidth conditions (all pairs, incl. movable peers) --
    for uid in app.units:
        for c in app.conds(uid, "network_proximity"):
            peer, lvl = c.get("related_unit"), c.get("unit") or c.get("value")
            for a in placement.get(uid, []):
                for b in placement.get(peer, []):
                    if not infra.proximity_ok(a, b, lvl):
                        violations.append(f"{uid} on {a} violates {lvl} proximity to {peer} on {b}")

    # ---- availability ---------------------------------------------------------
    target = app.sla.get("availability_target", 0)
    shortfall, avail = 0.0, {}
    for uid, nodes in placement.items():
        a = 1 - math.prod(1 - infra.nodes[n]["availability"] for n in set(nodes))
        avail[uid] = a
        if uid in app.movable:
            shortfall += max(0.0, target - a)
            # Hard mode is checked on the final plan (after replication), never on
            # anchored units: their availability is bounded by the device they need.
            if final and pl.get("availability_mode", "soft") == "hard" and a + EPS < target:
                violations.append(f"{uid}: availability {a:.4f} below hard target {target} (availability_mode=hard)")

    # ---- objective components ---------------------------------------------------
    dev = [util[n]["cpu_cores"] for n in util if infra.nodes[n]["tier"] == "device" and "cpu_cores" in util[n]]
    # Load balance is measured over the WHOLE pool of shared Edge/Cloud nodes (empty ones
    # included, other applications' load included), on each node's dominant resource.
    pool = [n for n, x in infra.nodes.items() if x["tier"] != "device" and x["comparable"]]
    def dom(n, extra):
        us = [(infra.used[n][r] + extra[r]) / infra.capacity(n, r)
              for r in RES if (infra.capacity(n, r) or 0) > 0]
        return max(us) if us else 0.0
    zero = {r: 0.0 for r in RES}
    dominant = {n: dom(n, load[n]) for n in pool}
    before = {n: dom(n, zero) for n in pool}
    std_after = statistics.pstdev(dominant.values()) if len(pool) > 1 else 0.0
    std_before = statistics.pstdev(before.values()) if len(pool) > 1 else 0.0
    max_after = max(dominant.values()) if pool else 0.0
    max_before = max(before.values()) if pool else 0.0
    cloud_cores = sum(load[n]["cpu_cores"] for n in app_nodes if infra.nodes[n]["tier"] == "cloud")
    risk = sum(1 for uid in app.movable if app.conds(uid, "verify_assumption")
               and any(n != app.units[uid]["original_host"] for n in placement.get(uid, [])))
    comp = {
        "network_traffic": total_traffic,
        "wan_traffic": wan,
        "latency": lat_cost,
        "device_load": max(dev) if dev else 0.0,
        # marginal effect of THIS application on the shared pool (load of previously
        # planned applications is a constant the application cannot change)
        "load_imbalance": std_after - std_before,
        "max_node_utilization": max_after - max_before,
        "cloud_usage": cloud_cores,
        "assumption_risk": risk,
        "availability_shortfall": shortfall,
    }
    norm = obj["normalization"]
    nkey = {"network_traffic": "network_traffic_mbps", "wan_traffic": "wan_traffic_mbps",
            "latency": "latency_cost_ms", "device_load": "device_load", "load_imbalance": "load_imbalance",
            "max_node_utilization": "max_node_utilization",
            "cloud_usage": "cloud_usage_cores", "assumption_risk": "assumption_risk_units",
            "availability_shortfall": "availability_shortfall"}
    score = sum(obj["weights"][k] * comp[k] / norm[nkey[k]] for k in comp)
    return (not violations), score, {"violations": violations, "components": comp, "node_load": load,
                                     "node_util": util, "link_load": link_load, "availability": avail,
                                     "pool_dominant_utilization": dominant,
                                     "pool_balance": {"stdev_before": std_before, "stdev_after": std_after,
                                                      "max_before": max_before, "max_after": max_after}}


def full_placement(app, primary, infra):
    """Add fixed units and followers to a movable-unit placement."""
    pl = {u: [n] for u, n in app.fixed.items()}
    pl.update({u: list(v) for u, v in primary.items()})
    for f in app.followers:
        hosts = []
        for s in app.units[f]["follows"]:
            for n in pl.get(s, []):
                if n not in hosts:
                    hosts.append(n)
        pl[f] = hosts
    return pl


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def search(app, infra, policy, cands):
    movable = app.movable
    space = math.prod(len(cands[u]) for u in movable) if movable else 1
    k = policy["planning"]["top_k_alternatives"]
    results, explored, method = [], 0, "exhaustive"
    if any(not cands[u] for u in movable):
        return [], 0, "no_candidates"
    if space <= policy["planning"]["max_exhaustive_candidates"]:
        for combo in itertools.product(*[cands[u] for u in movable]):
            explored += 1
            prim = {u: [n] for u, n in zip(movable, combo)}
            feas, score, det = evaluate(app, infra, full_placement(app, prim, infra), policy)
            if feas:
                results.append((score, prim, det))
    else:
        method = "greedy+local_search"
        prim, greedy_explored = greedy(app, infra, policy, cands, return_evaluations=True)
        explored += greedy_explored
        if prim:
            improved = True
            while improved:
                improved = False
                base = evaluate(app, infra, full_placement(app, prim, infra), policy)
                explored += 1
                for u in movable:
                    for n in cands[u]:
                        if [n] == prim[u]:
                            continue
                        trial = dict(prim)
                        trial[u] = [n]
                        explored += 1
                        f, s, d = evaluate(app, infra, full_placement(app, trial, infra), policy)
                        if f and s < base[1] - EPS:
                            prim, base, improved = trial, (f, s, d), True
            f, s, d = evaluate(app, infra, full_placement(app, prim, infra), policy)
            explored += 1
            if f:
                results.append((s, prim, d))
    results.sort(key=lambda x: x[0])
    return results[:policy['planning'].get('max_replicated_candidates', 5000)], explored, method


def greedy(app, infra, policy, cands, return_evaluations=False):
    """First-fit on candidates ordered by preference (current host, same site, edge, cloud)."""
    prim = {}
    explored = 0
    order = sorted(app.movable, key=lambda u: -sum(app.demand(u).values()))
    for u in order:
        best = None
        for n in cands[u]:
            trial = dict(prim)
            trial[u] = [n]
            partial = {x: trial[x] for x in trial}
            f, s, _ = evaluate(app, infra, full_placement_partial(app, partial), policy)
            explored += 1
            if f and (best is None or s < best[0]):
                best = (s, n)
        if best is None:
            return (None, explored) if return_evaluations else None
        prim[u] = [best[1]]
    return (prim, explored) if return_evaluations else prim


def full_placement_partial(app, primary):
    pl = {u: [n] for u, n in app.fixed.items()}
    pl.update(primary)
    return pl


# --------------------------------------------------------------------------- #
# Replication and load distribution
# --------------------------------------------------------------------------- #
DEFAULT_REPLICATION_MODELS = {
    # how each replication semantics divides the workload among k replicas
    "load_split":  {"writes": "split", "reads": "load_balanced", "cpu": "split", "storage": "full"},
    "mirrored":    {"writes": "all_replicas", "reads": "load_balanced", "cpu": "full", "storage": "full"},
    "partitioned": {"writes": "split", "reads": "load_balanced", "cpu": "split", "storage": "split"},
    "single":      {"writes": "n/a", "reads": "n/a", "cpu": "full", "storage": "full"},
}


def replication_model(policy, sem):
    m = dict(DEFAULT_REPLICATION_MODELS[sem])
    m.update(policy["planning"].get("replication_models", {}).get(sem, {}))
    return m


SEMANTICS_NOTE = {
    "load_split": "Replication semantics: load_split (stateless) - incoming traffic and CPU work are divided among the {k} replicas.",
    "mirrored": ("Replication semantics: mirrored - the unit holds persistent data, so every replica receives ALL writes "
                 "and keeps a full copy ({k}x write traffic, full CPU and storage per replica). ASSUMPTION: replicas "
                 "are kept consistent by asynchronous write replication; ordering/consistency is not modelled."),
    "partitioned": ("Replication semantics: partitioned - the persistent data is sharded; each of the {k} replicas "
                    "receives and stores 1/{k} of the records (no redundancy of individual records)."),
    "single": "",
}


def replicate(app, infra, policy, primary, cands):
    """Add replicas per the SLA policy.
    replication_policy = sla_required : add the desired replicas (anti-affinity) whatever the score
    replication_policy = score_driven : add a replica only if it lowers the objective score"""
    notes = []
    mode = policy["planning"].get("replication_policy", "sla_required")
    prim = {u: list(v) for u, v in primary.items()}
    for uid in app.movable:
        rule = app.sla.get("units", {}).get(uid, {})
        desired = int(rule.get("desired_replicas", 1))
        mx = int(rule.get("max_replicas", desired))
        k = min(desired, mx)
        sem = app.replication_semantics(uid, policy)
        if k > 1 and sem == "single":
            why = ("the unit is stateful (allow_stateful_replication=false)" if app.is_stateful(uid)
                   else "it holds persistent data (persistent_replication=disallowed)")
            notes.append(f"{uid}: {k} replicas requested but kept at 1 because {why}")
            k = 1
        while len(prim[uid]) < k:
            best = None
            current = evaluate(app, infra, full_placement(app, prim, infra), policy)[1]
            for n in cands[uid]:
                if n in prim[uid]:
                    continue  # anti-affinity: one replica per node
                trial = {u: list(v) for u, v in prim.items()}
                trial[uid].append(n)
                f, s, _ = evaluate(app, infra, full_placement(app, trial, infra), policy)
                if f and (best is None or s < best[0]):
                    best = (s, n)
            if best is None:
                notes.append(f"{uid}: only {len(prim[uid])} of {k} requested replicas could be placed "
                             f"(no other feasible node; anti-affinity allows one replica per node)")
                break
            if mode == "score_driven" and best[0] >= current - EPS:
                notes.append(f"{uid}: replica {len(prim[uid]) + 1} not added: it would raise the score "
                             f"from {current:.4f} to {best[0]:.4f} (replication_policy=score_driven)")
                break
            prim[uid].append(best[1])
        if len(prim[uid]) > 1:
            notes.append(f"{uid}: {len(prim[uid])} replicas on {', '.join(prim[uid])} because the SLA policy requests "
                         f"desired_replicas={desired} (max {mx}) for {app.name}; one replica per node (anti-affinity). "
                         + SEMANTICS_NOTE[sem].format(k=len(prim[uid])))
    return prim, notes


# --------------------------------------------------------------------------- #
# Baselines
# --------------------------------------------------------------------------- #
def baselines(app, infra, policy, cands):
    out = {}
    local = {u: [app.units[u]["original_host"]] for u in app.movable if app.units[u]["original_host"]}
    if len(local) == len(app.movable):
        f, s, d = evaluate(app, infra, full_placement(app, local, infra), policy)
        out["all_local"] = {"feasible": f, "score": round(s, 4), "violations": d["violations"],
                            "placement": {u: v[0] for u, v in local.items()}}
    else:
        out["all_local"] = {"feasible": False, "score": None,
                            "violations": ["some movable units have no current host in the infrastructure bindings"]}
    cloud = [n for n, x in infra.nodes.items() if x["tier"] == "cloud"]
    if cloud:
        pl = {u: [cloud[0]] for u in app.movable}
        f, s, d = evaluate(app, infra, full_placement(app, pl, infra), policy)
        out["cloud_only"] = {"feasible": f, "score": round(s, 4), "violations": d["violations"],
                             "placement": {u: cloud[0] for u in app.movable}}
    g = greedy(app, infra, policy, cands) if all(cands[u] for u in app.movable) else None
    if g:
        g, _ = replicate(app, infra, policy, g, cands)  # same replication policy as the optimizer
        f, s, d = evaluate(app, infra, full_placement(app, g, infra), policy)
        out["greedy_first_fit"] = {"feasible": f, "score": round(s, 4), "placement": {u: v for u, v in g.items()}}
    else:
        out["greedy_first_fit"] = {"feasible": False, "score": None}
    return out


# --------------------------------------------------------------------------- #
# Planning one application
# --------------------------------------------------------------------------- #
def plan_app(app, infra, policy):
    cands, rejected = generate_candidates(app, infra)
    top, explored, method = search(app, infra, policy, cands)
    base = baselines(app, infra, policy, cands)
    result = {
        "application_id": app.name,
        "search": {"method": method, "configurations_evaluated": explored,
                   "candidate_nodes": cands, "rejected_nodes": rejected},
        "baselines": base,
    }
    if not top:
        result["status"] = "infeasible"
        result["explanation"] = "No configuration satisfies resources, offloadability and network constraints."
        return result

    # Replication is part of the optimisation: every feasible base configuration is
    # replicated according to the policy, and the plan with the lowest FINAL score wins.
    finals, last_violations = [], []
    for score0, prim0, _ in top:
        prim, rep_notes = replicate(app, infra, policy, prim0, cands)
        placement = full_placement(app, prim, infra)
        feas, score, det = evaluate(app, infra, placement, policy, final=True)
        if feas:
            finals.append((score, score0, prim, rep_notes, placement, det))
        else:
            last_violations = det["violations"]
    if not finals:
        result["status"] = "infeasible"
        result["explanation"] = ("No configuration remains feasible after replication: "
                                 + "; ".join(last_violations))
        return result
    finals.sort(key=lambda x: x[0])
    # the same plan can be reached from different base configurations: keep one of each
    seen, unique = set(), []
    for f in finals:
        key = tuple(sorted((u, tuple(sorted(v))) for u, v in f[2].items()))
        if key not in seen:
            seen.add(key)
            unique.append(f)
    finals = unique
    score, score0, prim, rep_notes, placement, det = finals[0]
    feas = True
    result["search"]["base_configurations_feasible"] = len(top)
    result["search"]["replicated_configurations_feasible"] = len(finals)
    result["search"]["replication_policy"] = policy["planning"].get("replication_policy", "sla_required")

    rationale = decision_rationale(app, infra, policy, prim, placement, score, det, cands, rejected)

    # commit to residual infrastructure
    for nid, l in det["node_load"].items():
        for r in RES:
            infra.used[nid][r] += l[r]
    for lid, v in det["link_load"].items():
        infra.link_used[lid] += v

    units = []
    for uid, u in app.units.items():
        nodes = placement.get(uid, [])
        role = ("anchored" if uid in app.fixed else "follows " + ",".join(u["follows"]) if uid in app.followers
                else "offloaded" if any(n != u["original_host"] for n in nodes) else "kept on original host")
        units.append({
            "unit_id": uid, "name": u["name"], "offloadability": u["status"], "decision": role,
            "original_host": u["original_host"],
            # what is deployed ('single' when one instance) vs how the unit WOULD share work if replicated
            "replication_semantics": (None if uid not in app.movable else
                                      "single" if len(nodes) == 1 else app.replication_semantics(uid, policy)),
            "replicable_as": app.replication_semantics(uid, policy) if uid in app.movable else None,
            "decision_rationale": rationale.get(uid),
            "replicas": [{"node": n, "tier": infra.nodes[n]["tier"], "site": infra.nodes[n]["site"]} for n in nodes],
            "per_replica_share": replica_shares(app, uid, nodes, policy),
            "availability": round(det["availability"].get(uid, 0), 5),
            "meets_availability_target": det["availability"].get(uid, 0) + EPS >= app.sla.get("availability_target", 0),
            "availability_cause": availability_cause(app, infra, uid, nodes, det, policy),
            "open_assumptions": [c["requirement"] for c in app.conds(uid, "verify_assumption")],
        })
    target = app.sla.get("availability_target", 0)
    below = [{"unit_id": u["unit_id"], "availability": u["availability"], "target": target,
              "controllable_by_planner": u["unit_id"] in app.movable, "cause": u["availability_cause"]}
             for u in units if not u["meets_availability_target"]]
    mode = policy["planning"].get("availability_mode", "soft")
    result.update({
        "status": "feasible",
        "sla_compliance": {
            "availability_mode": mode,
            "availability_target": target,
            "availability": ("met" if not below else
                             "met_for_controllable_units" if not any(b["controllable_by_planner"] for b in below)
                             else "not_met_soft_constraint"),
            "units_below_target": below,
            "explanation": ("Availability is a soft objective: shortfalls of movable units are penalised in the score "
                            "but do not make the plan infeasible." if mode == "soft" else
                            "Availability is a hard constraint for movable units (checked after replication).")
                           + " Anchored units are excluded from the constraint: their availability is bounded by the "
                             "device they depend on, which the planner cannot change.",
        },
        "placements": units,
        "objective": {"score": round(score, 4), "score_before_replication": round(score0, 4),
                      "components": {k: round(v, 6) for k, v in det["components"].items()}},
        "violations": det["violations"],
        "node_utilization": {n: {r: round(v, 3) for r, v in u.items()} for n, u in det["node_util"].items()},
        "load_balance": {
            "pool": "all shared Edge and Cloud nodes, including load of previously planned applications",
            "metric": "dominant resource utilization per node = max over CPU, memory, GPU memory, storage",
            "replication_models": {sem: replication_model(policy, sem) for sem in DEFAULT_REPLICATION_MODELS},
            "dominant_utilization": {n: round(v, 4) for n, v in det["pool_dominant_utilization"].items()},
            "max_node_utilization": {"before": round(det["pool_balance"]["max_before"], 4),
                                     "after": round(det["pool_balance"]["max_after"], 4)},
            "stdev": {"before": round(det["pool_balance"]["stdev_before"], 4),
                      "after": round(det["pool_balance"]["stdev_after"], 4)},
            "objective_uses": "after - before (marginal effect of this application)",
        },
        "link_load_mbps": {l: round(v, 6) for l, v in det["link_load"].items() if v > 0},
        "replication_notes": rep_notes,
        "alternatives": [{"score": round(fs, 4), "score_before_replication": round(bs, 4),
                          "placement": {u: v for u, v in p.items()}}
                         for fs, bs, p, _, _, _ in finals[1:policy["planning"]["top_k_alternatives"] + 1]],
    })
    return result


def replica_shares(app, uid, nodes, policy):
    """Workload handled by EACH replica, derived from the same replication model as evaluate()."""
    k = len(nodes)
    if k == 0:
        return None
    sem = app.replication_semantics(uid, policy) if uid in app.movable else "single"
    m = replication_model(policy, sem)
    if k == 1:
        return {"semantics": "single", "replicable_as": sem, "replicas": 1, "writes": "n/a (single instance)", "reads": "n/a (single instance)",
                "write_traffic_share": 1.0, "read_traffic_share": 1.0, "cpu_share": 1.0, "storage_share": 1.0}
    share = round(1 / k, 3)
    return {
        "semantics": sem,
        "replicas": k,
        "writes": m["writes"],                 # all_replicas = mirrored, split = divided
        "reads": m["reads"],                   # load_balanced or primary
        "write_traffic_share": 1.0 if m["writes"] == "all_replicas" else share,
        "read_traffic_share": (share if m["reads"] == "load_balanced" else "1.0 on primary, 0 on others"),
        "cpu_share": share if m["cpu"] == "split" else 1.0,
        "storage_share": share if m["storage"] == "split" else 1.0,
        "note": {"mirrored": "writes are mirrored to every replica (full copy each); reads are served by one replica",
                 "load_split": "requests and CPU work divided among replicas; each replica loads its own code/models",
                 "partitioned": "data sharded: each replica receives and stores 1/k of the records"}.get(sem),
    }


def _top_deltas(base, other, policy, n=2):
    """The objective components that change most between two configurations."""
    w, norm = policy["objective"]["weights"], policy["objective"]["normalization"]
    nk = {"network_traffic": "network_traffic_mbps", "wan_traffic": "wan_traffic_mbps", "latency": "latency_cost_ms",
          "device_load": "device_load", "load_imbalance": "load_imbalance", "max_node_utilization": "max_node_utilization",
          "cloud_usage": "cloud_usage_cores", "assumption_risk": "assumption_risk_units",
          "availability_shortfall": "availability_shortfall"}
    d = {k: w[k] * (other[k] - base[k]) / norm[nk[k]] for k in base if k in w}
    return [f"{k} {'+' if v > 0 else ''}{v:.3g}" for k, v in sorted(d.items(), key=lambda x: -abs(x[1]))[:n] if abs(v) > 1e-6]


def decision_rationale(app, infra, policy, prim, placement, score, det, cands, rejected):
    """Why each unit ended up where it is: constraints that restrict it, and what moving
    it (everything else unchanged) would cost or break."""
    out = {}
    for uid, u in app.units.items():
        if uid in app.fixed:
            node = app.fixed[uid]
            bf = [f"{b.get('type')}: {b.get('evidence', '')}" for b in u.get("blocking_factors", [])]
            out[uid] = {"reason": f"anchored: non_offloadable, bound to anchor {u['anchored_to']} on {node}",
                        "blocking_factors": bf}
            continue
        if uid in app.followers:
            hosts = placement.get(uid, [])
            st = app.demand(uid)["storage_gb"]
            out[uid] = {"reason": (f"initialization dependency of {', '.join(u['follows'])} "
                                   f"(offloadability: follows_supported_units): deployed on every node hosting "
                                   f"one of them ({', '.join(hosts)}), so that each consumer loads its models "
                                   f"locally. Not placed independently and not scaled on its own; only its "
                                   f"persistent storage ({st:g} GB) is reserved, and its start-up peak must fit.")}
            continue
        # movable unit: counterfactual moves
        base_comp = det["components"]
        alts = []
        for i, cur in enumerate(prim[uid]):
            for n in cands[uid]:
                if n in prim[uid]:
                    continue
                trial = {x: list(v) for x, v in prim.items()}
                trial[uid][i] = n
                f, s2, d2 = evaluate(app, infra, full_placement(app, trial, infra), policy, final=True)
                alts.append({"move": f"{cur} -> {n}", "feasible": f,
                             "score_delta": round(s2 - score, 4) if f else None,
                             "why": (_top_deltas(base_comp, d2["components"], policy) if f
                                     else d2["violations"][:2])})
        feasible_alts = sorted([a for a in alts if a["feasible"]], key=lambda a: a["score_delta"])
        infeasible = [a for a in alts if not a["feasible"]]
        grouped_rej = {}
        for n, why in rejected[uid].items():
            grouped_rej.setdefault(why, []).append(n)
        chosen = ", ".join(prim[uid])
        if not alts:
            summary = f"{chosen} is the only candidate node that satisfies the unit-level conditions."
        elif not feasible_alts:
            summary = f"{chosen}: every other candidate node violates a constraint (see infeasible_moves)."
        else:
            b = feasible_alts[0]
            summary = (f"{chosen} minimises the objective; the closest alternative ({b['move']}) "
                       f"scores +{b['score_delta']} ({'; '.join(b['why']) or 'negligible difference'}).")
        out[uid] = {
            "reason": summary,
            "excluded_before_search": [{"reason": why, "nodes": ns} for why, ns in grouped_rej.items()],
            "closest_feasible_alternatives": feasible_alts[:3],
            "infeasible_moves": infeasible[:5],
            "infeasible_moves_total": len(infeasible),
        }
    return out


def availability_cause(app, infra, uid, nodes, det, policy):
    target = app.sla.get("availability_target", 0)
    a = det["availability"].get(uid, 0)
    if a + EPS >= target:
        return None
    if uid in app.fixed:
        n = app.fixed[uid]
        return f"anchored to {n}; bounded by the device availability ({infra.nodes[n]['availability']})"
    if uid in app.followers:
        return "follows " + ", ".join(app.units[uid]["follows"]) + "; inherits their placement"
    rule = app.sla.get("units", {}).get(uid, {})
    desired = int(rule.get("desired_replicas", 1))
    if app.is_stateful(uid) and not policy["planning"]["allow_stateful_replication"]:
        return "stateful unit kept at one instance (allow_stateful_replication = false)"
    if len(nodes) < desired:
        return f"only {len(nodes)} of {desired} requested replicas could be placed"
    hosts = ", ".join(f"{n} ({infra.nodes[n]['availability']})" for n in nodes)
    return (f"SLA requests {desired} replica(s); placed on {hosts}, whose availability is below the target. "
            f"The shortfall is penalised in the objective (soft mode).")


def main():
    infra = Infrastructure(load_json(BASE / "infrastructure.json"))
    policy = load_json(BASE / "sla_policy.json")
    apps = sys.argv[1:] or APPS
    apps = sorted(apps, key=lambda a: policy["applications"].get(a, {}).get("priority", 99))
    out_dir = BASE / "output"
    out_dir.mkdir(exist_ok=True)

    plans = {}
    for name in apps:
        app = Application(name, infra, policy)
        plans[name] = plan_app(app, infra, policy)
        with open(out_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(plans[name], f, indent=2)
        p = plans[name]
        print(f"\n=== {name}: {p['status']}  ({p['search']['method']}, {p['search']['configurations_evaluated']} configurations)")
        for u in p.get("placements", []):
            print(f"  {u['unit_id']:<4} {u['decision']:<22} -> {', '.join(r['node'] for r in u['replicas'])}")
        if "objective" in p:
            print(f"  score {p['objective']['score']}  |  " +
                  "  ".join(f"{k}={v:.3g}" for k, v in p["objective"]["components"].items() if v))
        for bn, b in p["baselines"].items():
            print(f"  baseline {bn:<17} feasible={b['feasible']}  score={b['score']}")
        for n in p.get("replication_notes", []):
            print(f"  note: {n}")

    summary = {
        "applications": list(plans),
        "node_usage": {n: {r: round(v, 3) for r, v in u.items() if v > 0}
                       for n, u in infra.used.items() if any(v > 0 for v in u.values())},
        "link_usage_mbps": {l: round(v, 6) for l, v in infra.link_used.items() if v > 0},
    }
    with open(out_dir / "joint_plan_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nPlans written to {out_dir}")


if __name__ == "__main__":
    main()
