"""Generate synthetic planner workloads and measure exhaustive/heuristic search."""

from __future__ import annotations

import argparse
import copy
import csv
import importlib.util
import itertools
import json
import math
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
OUTPUT = EXPERIMENTS / "output" / "rq2_scalability"
DEFAULT_M = (2, 3, 4, 5)
DEFAULT_N = (8, 16, 24)
DEFAULT_LARGE = ((10, 32), (20, 64), (40, 100))
GPU_PROBABILITY = 0.20
STATEFUL_PROBABILITY = 0.20
PROXIMITY_PROBABILITY = 0.50
EXTRA_EDGE_PROBABILITY = 0.10
EDGE_BANDWIDTH_MBPS = 0.01


def load_planner():
    path = ROOT / "deployment" / "deployment_planner.py"
    spec = importlib.util.spec_from_file_location("deployment_planner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load planner module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dp = load_planner()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def make_instance(movable_count: int, edge_count: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    app_name = f"synthetic_m{movable_count}_n{edge_count}_s{seed}"
    unit_ids = [f"U{i}" for i in range(movable_count + 1)]
    components = ["anchor"] + [f"task_{i}" for i in range(1, movable_count + 1)]
    graph_edges = [
        {"source": components[i], "target": components[i + 1], "type": "data_flow"}
        for i in range(movable_count)
    ]
    for source in range(movable_count + 1):
        for target in range(source + 2, movable_count + 1):
            if rng.random() < EXTRA_EDGE_PROBABILITY:
                graph_edges.append({
                    "source": components[source],
                    "target": components[target],
                    "type": "data_flow",
                })

    gpu_units = set()
    stateful_units = set()
    proximity_units = set()
    for index in range(1, movable_count + 1):
        if rng.random() < GPU_PROBABILITY:
            gpu_units.add(index)
        if rng.random() < STATEFUL_PROBABILITY:
            stateful_units.add(index)
        if rng.random() < PROXIMITY_PROBABILITY:
            proximity_units.add(index)

    profiles = [{
        "unit_id": "U0",
        "name": "Anchored source",
        "unit_type": "runtime",
        "cpu": {"level": "very_low", "provenance": "inferred", "typical_cores": 0.05, "peak_cores": 0.1},
        "memory": {"level": "very_low", "provenance": "inferred", "typical_gb": 0.05, "peak_gb": 0.1},
        "gpu": {"requirement": "none", "memory_gb": 0},
        "storage": {"level": "very_low", "size_gb": 0, "persistent": False, "growth": "none"},
        "network": {"physical_ingress_mbps": 0, "physical_egress_mbps": 0,
                    "potential_ingress_mbps": EDGE_BANDWIDTH_MBPS,
                    "potential_egress_mbps": EDGE_BANDWIDTH_MBPS},
    }]
    offload_profiles = [{
        "unit_id": "U0", "name": "Anchored source", "unit_type": "runtime",
        "status": "non_offloadable", "anchored_to": "A1", "conditions": [],
        "follows_units": [],
    }]
    for index in range(1, movable_count + 1):
        gpu_required = index in gpu_units
        persistent = index == movable_count
        profile = {
            "unit_id": unit_ids[index],
            "name": f"Synthetic task {index}",
            "unit_type": "runtime",
            "cpu": {"level": "low", "provenance": "assumed", "typical_cores": 0.25, "peak_cores": 0.5},
            "memory": {"level": "low", "provenance": "assumed", "typical_gb": 0.25, "peak_gb": 0.5},
            "gpu": {"requirement": "required" if gpu_required else "none",
                    "memory_gb": 2 if gpu_required else 0},
            "storage": {"level": "low" if persistent else "very_low",
                        "size_gb": 0.5 if persistent else 0,
                        "persistent": persistent,
                        "growth": "grows_over_time" if persistent else "none"},
            "network": {"physical_ingress_mbps": 0, "physical_egress_mbps": 0,
                        "potential_ingress_mbps": EDGE_BANDWIDTH_MBPS,
                        "potential_egress_mbps": EDGE_BANDWIDTH_MBPS},
        }
        conditions = []
        if gpu_required:
            conditions.append({"type": "gpu_required", "value": 2, "unit": "GB", "related_unit": None})
        if index in proximity_units:
            conditions.append({"type": "network_proximity", "value": "same_site",
                               "unit": "same_site", "related_unit": "U0"})
        if index in stateful_units:
            conditions.append({"type": "state_handling", "value": None, "unit": None, "related_unit": None})
        if persistent:
            conditions.append({"type": "persistent_storage", "value": 0.5, "unit": "GB", "related_unit": None})
        profiles.append(profile)
        offload_profiles.append({
            "unit_id": unit_ids[index],
            "name": profile["name"],
            "unit_type": "runtime",
            "status": "conditionally_offloadable" if conditions else "offloadable",
            "anchored_to": None,
            "conditions": conditions,
            "follows_units": [],
        })

    communication = []
    for edge in graph_edges:
        source_index = components.index(edge["source"])
        target_index = components.index(edge["target"])
        communication.append({
            "source": unit_ids[source_index],
            "target": unit_ids[target_index],
            "bandwidth_mbps": EDGE_BANDWIDTH_MBPS,
            "boundary": "logical",
            "latency_sensitivity": "medium",
        })

    resource_document = {"application_id": app_name, "resource_profiles": profiles,
                         "communication_requirements": communication}
    offloadability_document = {"application_id": app_name, "anchors": [{
        "anchor_id": "A1", "anchored_units": ["U0"],
        "network_connectivity": "IP network", "provenance": "assumed",
    }], "offloadability_profiles": offload_profiles}
    infrastructure = make_infrastructure(edge_count, app_name)
    policy = make_policy(app_name, movable_count)
    graph_document = {"application_id": app_name,
                      "nodes": [{"id": component, "name": component, "function": component}
                                for component in components],
                      "edges": graph_edges}
    return {
        "name": app_name,
        "m": movable_count,
        "n": edge_count,
        "seed": seed,
        "graph": graph_document,
        "resource": resource_document,
        "offloadability": offloadability_document,
        "infrastructure": infrastructure,
        "policy": policy,
        "gpu_units": sorted(unit_ids[i] for i in gpu_units),
        "stateful_units": sorted(unit_ids[i] for i in stateful_units),
        "proximity_units": sorted(unit_ids[i] for i in proximity_units),
    }


def make_infrastructure(edge_count: int, app_name: str) -> dict[str, Any]:
    local_count = (edge_count + 1) // 2
    sites = [
        {"id": "local", "region": "region_a", "description": "Local Edge site"},
        {"id": "metro", "region": "region_a", "description": "Metropolitan Edge site"},
        {"id": "cloud", "region": "cloud", "description": "Cloud site"},
    ]
    nodes = [{
        "id": "anchor_node", "tier": "device", "site": "local", "kind": "device",
        "comparable": True, "internet_access": True, "availability": 0.98,
        "capacity": {"cpu_cores": 4, "memory_gb": 8, "gpu_memory_gb": 0,
                     "storage_gb": 10},
    }]
    links = []
    for index in range(edge_count):
        site = "local" if index < local_count else "metro"
        gpu_mem = 8 if index % 4 == 0 else 0
        node_id = f"edge_{index + 1}"
        nodes.append({
            "id": node_id, "tier": "edge", "site": site, "kind": "server",
            "comparable": True, "internet_access": True, "availability": 0.99,
            "capacity": {"cpu_cores": 32, "memory_gb": 128,
                         "gpu_memory_gb": gpu_mem, "storage_gb": 1000},
        })
        links.append({"id": f"edge_link_{index + 1}", "a": node_id,
                      "b": "local_switch" if site == "local" else "metro_switch",
                      "type": "lan", "bandwidth_mbps": 10000, "latency_ms": 0.2})
    nodes.extend([
        {"id": "local_switch", "tier": "switch", "site": "local", "kind": "switch",
         "comparable": False, "internet_access": True, "availability": 1.0,
         "capacity": {"cpu_cores": 0, "memory_gb": 0, "gpu_memory_gb": 0, "storage_gb": 0}},
        {"id": "metro_switch", "tier": "switch", "site": "metro", "kind": "switch",
         "comparable": False, "internet_access": True, "availability": 1.0,
         "capacity": {"cpu_cores": 0, "memory_gb": 0, "gpu_memory_gb": 0, "storage_gb": 0}},
        {"id": "cloud_switch", "tier": "switch", "site": "cloud", "kind": "switch",
         "comparable": False, "internet_access": True, "availability": 1.0,
         "capacity": {"cpu_cores": 0, "memory_gb": 0, "gpu_memory_gb": 0, "storage_gb": 0}},
        {"id": "cloud_1", "tier": "cloud", "site": "cloud", "kind": "server",
         "comparable": True, "internet_access": True, "availability": 0.999,
         "capacity": {"cpu_cores": 128, "memory_gb": 512,
                      "gpu_memory_gb": 24, "storage_gb": 10000}},
    ])
    links.extend([
        {"id": "anchor_link", "a": "anchor_node", "b": "local_switch",
         "type": "lan", "bandwidth_mbps": 10000, "latency_ms": 0.2},
        {"id": "local_metro_wan", "a": "local_switch", "b": "metro_switch",
         "type": "wan", "bandwidth_mbps": 10000, "latency_ms": 5},
        {"id": "metro_cloud_wan", "a": "metro_switch", "b": "cloud_switch",
         "type": "wan", "bandwidth_mbps": 10000, "latency_ms": 40},
        {"id": "cloud_link", "a": "cloud_1", "b": "cloud_switch",
         "type": "lan", "bandwidth_mbps": 10000, "latency_ms": 0.2},
    ])
    return {
        "description": "Generated two-tier Edge and Cloud infrastructure.",
        "sites": sites,
        "nodes": nodes,
        "links": links,
        "application_bindings": {
            app_name: {"anchors": {"A1": "anchor_node"},
                       "original_host": {"U0": "anchor_node"}},
        },
    }


def make_policy(app_name: str, movable_count: int) -> dict[str, Any]:
    policy = load_json(ROOT / "deployment" / "sla_policy.json")
    policy["applications"] = {
        app_name: {
            "priority": 1,
            "availability_target": 0.95,
            "units": {f"U{i}": {"desired_replicas": 1, "max_replicas": 1}
                      for i in range(1, movable_count + 1)},
        }
    }
    return policy


def config_space(instance: dict[str, Any]) -> tuple[int, dict[str, list[str]]]:
    infra = dp.Infrastructure(copy.deepcopy(instance["infrastructure"]))
    app = dp.Application(instance["name"], infra, instance["policy"],
                         instance["resource"], instance["offloadability"])
    candidates, _ = dp.generate_candidates(app, infra)
    space = math.prod(len(candidates[unit]) for unit in app.movable) if app.movable else 1
    return space, candidates


def choose_exact_instance(m: int, n: int, seed: int, limit: int,
                          attempts: int = 1000) -> tuple[dict[str, Any], int, dict[str, list[str]]]:
    for offset in range(attempts):
        instance = make_instance(m, n, seed + offset)
        space, candidates = config_space(instance)
        if space <= limit and all(candidates.values()):
            instance["generation_attempt"] = offset + 1
            return instance, space, candidates
    raise RuntimeError(f"No feasible paired instance for m={m}, N={n} fit the exact-search cap "
                       f"of {limit} configurations after {attempts} deterministic seeds")


def run_once(instance: dict[str, Any], mode: str, exact_limit: int) -> dict[str, Any]:
    infra = dp.Infrastructure(copy.deepcopy(instance["infrastructure"]))
    policy = copy.deepcopy(instance["policy"])
    policy["planning"]["max_exhaustive_candidates"] = exact_limit if mode == "exhaustive" else 0
    app = dp.Application(instance["name"], infra, policy,
                         instance["resource"], instance["offloadability"])
    start = time.perf_counter()
    plan = dp.plan_app(app, infra, policy)
    elapsed = time.perf_counter() - start
    objective = plan.get("objective", {}).get("score")
    return {
        "elapsed_seconds": elapsed,
        "method": plan.get("search", {}).get("method"),
        "configurations_evaluated": plan.get("search", {}).get("configurations_evaluated"),
        "feasible": plan.get("status") == "feasible",
        "objective_score": objective,
    }


def gap(exact_score: Optional[float], heuristic_score: Optional[float]) -> Optional[float]:
    if exact_score is None or heuristic_score is None:
        return None
    if abs(exact_score) < 1e-12:
        return 0.0 if abs(heuristic_score) < 1e-12 else None
    return (heuristic_score - exact_score) / abs(exact_score)


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    times = [sample["elapsed_seconds"] for sample in samples]
    counts = [sample["configurations_evaluated"] for sample in samples]
    scores = [sample["objective_score"] for sample in samples if sample["objective_score"] is not None]
    return {
        "repetitions": len(samples),
        "runtime_median_seconds": statistics.median(times),
        "runtime_min_seconds": min(times),
        "runtime_max_seconds": max(times),
        "configurations_evaluated_median": statistics.median(counts),
        "feasible_repetitions": sum(sample["feasible"] for sample in samples),
        "objective_score_median": statistics.median(scores) if scores else None,
        "samples": samples,
    }


def save_instance(instance: dict[str, Any], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    serializable = {key: value for key, value in instance.items() if key != "policy"}
    serializable["policy"] = instance["policy"]
    (folder / "instance.json").write_text(json.dumps(serializable, indent=2) + "\n", encoding="utf-8")


def benchmark_small(m_values: tuple[int, ...], n_values: tuple[int, ...],
                    repetitions: int, seed: int, exact_limit: int,
                    output: Path, existing_rows: Optional[list[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    rows = list(existing_rows or [])
    completed = {
        (row["m"], row["N"])
        for row in rows
        if row["case"] in ("small_paired", "small_heuristic_only")
    }
    for m in m_values:
        for n in n_values:
            if (m, n) in completed:
                print(f"[small] m={m} N={n} already saved; skipping", flush=True)
                continue
            instance, space, candidates = choose_exact_instance(
                m, n, seed + m * 1009 + n, exact_limit
            )
            save_instance(instance, output / "instances" / f"m{m}_N{n}_seed{instance['seed']}")
            exact_possible = True
            modes = ("exhaustive", "heuristic")
            print(f"[small] m={m} N={n} candidates={space} modes={','.join(modes)}", flush=True)
            samples_by_mode = {mode: [] for mode in modes}
            gaps = []
            for _ in range(repetitions):
                exact = run_once(instance, "exhaustive", exact_limit) if exact_possible else None
                heuristic = run_once(instance, "heuristic", exact_limit)
                if exact is not None:
                    samples_by_mode["exhaustive"].append(exact)
                    gaps.append(gap(exact["objective_score"], heuristic["objective_score"]))
                samples_by_mode["heuristic"].append(heuristic)
            for mode in modes:
                summary = summarize(samples_by_mode[mode])
                rows.append({
                    "case": "small_paired" if exact_possible else "small_heuristic_only",
                    "m": m, "N": n,
                    "seed": instance["seed"], "candidate_space": space,
                    "mode": mode, "search_method": samples_by_mode[mode][0]["method"],
                    **{key: value for key, value in summary.items() if key != "samples"},
                    "optimality_gap_median": (
                        0.0 if mode == "exhaustive" else None if not exact_possible else
                        statistics.median([value for value in gaps if value is not None])
                        if any(value is not None for value in gaps) else None
                    ),
                    "samples": summary["samples"],
                })
            write_results(rows, output, {
                "seed": seed, "repetitions": repetitions,
                "small_m_values": m_values, "small_N_values": n_values,
                "max_exact_configurations": exact_limit,
            })
    return rows


def benchmark_large(pairs: tuple[tuple[int, int], ...], repetitions: int,
                    seed: int, output: Path,
                    existing_rows: Optional[list[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    rows = list(existing_rows or [])
    completed = {
        (row["m"], row["N"])
        for row in rows if row["case"] == "large_heuristic_only"
    }
    for m, n in pairs:
        if (m, n) in completed:
            print(f"[large heuristic-only] m={m} N={n} already saved; skipping", flush=True)
            continue
        instance = make_instance(m, n, seed + m * 1009 + n)
        space, _ = config_space(instance)
        save_instance(instance, output / "instances" / f"m{m}_N{n}_seed{instance['seed']}")
        print(f"[large heuristic-only] m={m} N={n} candidates={space}", flush=True)
        samples = [run_once(instance, "heuristic", 0) for _ in range(repetitions)]
        summary = summarize(samples)
        rows.append({
            "case": "large_heuristic_only", "m": m, "N": n,
            "seed": instance["seed"], "candidate_space": space,
            "mode": "heuristic", "search_method": samples[0]["method"],
            **{key: value for key, value in summary.items() if key != "samples"},
            "optimality_gap_median": None,
            "samples": summary["samples"],
        })
        write_results(rows, output, {
            "seed": seed, "repetitions": repetitions,
            "max_exact_configurations": 200000,
        })
    return rows


def write_results(rows: list[dict[str, Any]], output: Path, metadata: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps({"metadata": metadata, "results": rows}, indent=2) + "\n", encoding="utf-8"
    )
    fields = [key for key, value in rows[0].items() if key != "samples" and not isinstance(value, (dict, list))]
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in rows)


def create_figures(rows: list[dict[str, Any]], output: Path) -> bool:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Matplotlib is unavailable; results were saved, but PDF figures were not generated.", file=sys.stderr)
        return False

    figure_dir = EXPERIMENTS / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(6.4, 4.2))
    for mode, marker in (("exhaustive", "o"), ("heuristic", "s")):
        selected = [row for row in rows if row["case"] == "small_paired" and row["mode"] == mode]
        axis.scatter([row["candidate_space"] for row in selected],
                     [row["runtime_median_seconds"] for row in selected],
                     label=mode.replace("_", " "), marker=marker)
    selected = [row for row in rows if row["case"] == "large_heuristic_only"]
    if selected:
        axis.scatter([row["candidate_space"] for row in selected],
                     [row["runtime_median_seconds"] for row in selected],
                     label="large heuristic only", marker="^")
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("Candidate configurations (product of candidate counts)")
    axis.set_ylabel("Median planner runtime (s)")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "fig_scalability_time.pdf")
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6.4, 4.2))
    for n in sorted({row["N"] for row in rows if row["case"] == "small_paired"}):
        selected = sorted(
            (row for row in rows if row["case"] == "small_paired" and row["mode"] == "heuristic" and row["N"] == n),
            key=lambda row: row["m"],
        )
        points = [row for row in selected if row["optimality_gap_median"] is not None]
        if points:
            axis.plot([row["m"] for row in points],
                      [100 * row["optimality_gap_median"] for row in points],
                      marker="o", label=f"N={n}")
    axis.axhline(0, color="black", linewidth=0.8)
    axis.set_xlabel("Movable units (m)")
    axis.set_ylabel("Heuristic optimality gap (%)")
    axis.grid(True, alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "fig_optimality_gap.pdf")
    plt.close(fig)
    return True


def parse_ints(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(",") if part.strip())


def parse_pairs(value: str) -> tuple[tuple[int, int], ...]:
    if not value.strip():
        return ()
    return tuple(tuple(int(item) for item in part.split(":")) for part in value.split(","))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m-values", default="2,3,4,5")
    parser.add_argument("--n-values", default="8,16,24")
    parser.add_argument("--large-pairs", default="10:32,20:64,40:100",
                        help="Comma-separated m:N cases for heuristic-only runs; empty disables them")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261002)
    parser.add_argument("--max-exact-configurations", type=int, default=200000)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--resume", action="store_true",
                        help="Keep completed cases from results.json and run only missing cases")
    parser.add_argument("--plot-only", action="store_true",
                        help="Render figures from the existing results.json without rerunning cases")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    if args.plot_only:
        result_path = args.output_dir / "results.json"
        data = load_json(result_path)
        if create_figures(data["results"], args.output_dir):
            print(f"PDF figures: {EXPERIMENTS / 'figures'}")
            return 0
        return 1

    m_values, n_values = parse_ints(args.m_values), parse_ints(args.n_values)
    large_pairs = parse_pairs(args.large_pairs)
    existing_rows = []
    if args.resume and (args.output_dir / "results.json").exists():
        existing_rows = load_json(args.output_dir / "results.json")["results"]
    rows = benchmark_small(m_values, n_values, args.repetitions, args.seed,
                           args.max_exact_configurations, args.output_dir, existing_rows)
    rows = benchmark_large(large_pairs, args.repetitions, args.seed, args.output_dir, rows)
    metadata = {
        "seed": args.seed,
        "repetitions": args.repetitions,
        "small_m_values": m_values,
        "small_N_values": n_values,
        "large_heuristic_only_pairs": large_pairs,
        "max_exact_configurations": args.max_exact_configurations,
        "probabilities": {
            "gpu_requirement": GPU_PROBABILITY,
            "stateful": STATEFUL_PROBABILITY,
            "proximity": PROXIMITY_PROBABILITY,
            "extra_edge": EXTRA_EDGE_PROBABILITY,
        },
        "timing_scope": "End-to-end plan_app call, including candidate generation, search, baselines, and replication.",
        "search_count_scope": "Configurations evaluated by the selected search algorithm; heuristic counts include greedy initialization, local-search evaluations, and final search scoring.",
        "python_version": sys.version,
        "platform": platform.platform(),
    }
    write_results(rows, args.output_dir, metadata)
    figures = False if args.no_plots else create_figures(rows, args.output_dir)
    print(f"Saved {len(rows)} benchmark rows to {args.output_dir}")
    print(f"CSV: {args.output_dir / 'results.csv'}")
    print(f"JSON: {args.output_dir / 'results.json'}")
    if figures:
        print(f"PDF figures: {EXPERIMENTS / 'figures'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())