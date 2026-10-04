# LLM Pre-Deployment Planner

A pre-deployment offloading pipeline for Edge–Cloud applications. Starting from
an application's **functional graph**, the pipeline decides *what* can be
offloaded, *where* each part should run on a shared Edge–Cloud infrastructure,
and *checks* the resulting plan before anything is deployed.

```
functional graph
      │
      ▼
 1. Granularity ─► 2. Resource Estimation ─► 3. Offloadability      (LLM, prompt-based)
                                                   │
                                                   ▼
                             4. Deployment Planner ─► 5. Validation   (deterministic Python)
                                      ▲                    │
                                      └──── feedback ◄─────┘
```

- **Stages 1–3** are executed by an LLM. They are **prompt-only and
  model-agnostic**: every stage is a Markdown prompt that can be pasted into any
  LLM (Claude, ChatGPT, Gemini, a local model, …). No API key or script is needed.
- **Stages 4–5** are deterministic Python scripts (standard library only).

## Evaluated applications

| Application | Description |
|---|---|
| `smart_surveillance` | Camera stream, object detection (GPU) and stateful tracking, event storage |
| `smart_agriculture_iot` | Arduino sensors and a smartphone, mostly device-bound units |
| `crop_monitoring` | Crop sensor data processing and persistent storage |

## Repository structure

```
granularity/            Stage 1 – splits the functional graph into execution units
  input/<app>.json        functional graph
  prompt.md               prompt template
  ready_prompts/<app>.md  prompt already filled with the input (paste into the LLM)
  output/<app>.json       LLM answer (execution units + unit graph)

resource_estimation/    Stage 2 – CPU, memory, GPU, storage and bandwidth per unit
  input/ prompt.md ready_prompts/ output/   (same layout)

offloadability/         Stage 3 – anchors, offloadability status and conditions
  input/ prompt.md ready_prompts/ output/   (same layout)

deployment/             Stage 4 – Deployment Planner
  deployment_planner.py
  infrastructure.json     shared infrastructure (sites, nodes, links, application bindings)
  sla_policy.json         planning rules, objective weights, per-application SLA
  output/<app>.json       deployment descriptor per application
  output/joint_plan_summary.json

validation/             Stage 5 – independent validator
  deployment_validator.py
  output/<app>.json       validation result per application
  output/joint_validation.json
  output/self_test.json   fault-injection results

experiments/
  experiment_summary.py           summary scripts for application and validation outputs
  requirements.txt                Python dependencies for benchmark scripts
  rq2_scalability_benchmark.py    synthetic benchmark for scalability experiments
  figures/                        generated plots for the experiments
  output/                         benchmark and summary results
    rq2_count_smoke/              smoke benchmark outputs
    rq2_sampling_smoke/            sample-size benchmark outputs
    rq2_scalability/              scalability benchmark outputs
    rq2_smoke/                    smoke benchmark outputs
    rq2_smoke2/                   additional smoke outputs
    rq2_smoke3/                   additional smoke outputs
    rq2_smoke_task/               task-based smoke outputs

```

## Requirements

- Python 3.9 or later. The planner and validator use only the standard library.
- Any LLM chat interface for stages 1–3.

## How to run

### Stages 1–3 (LLM)

Run the stages in order, since each stage uses the outputs of the previous ones
(they are already included in the next stage's `input/` and `ready_prompts/`).
For each application:

1. Open `<stage>/ready_prompts/<app>.md` and paste its whole content into the LLM.
2. Copy the JSON answer into `<stage>/output/<app>.json`.

To analyze a new application, write its functional graph in
`granularity/input/<app>.json`, then create `granularity/ready_prompts/<app>.md`
by copying the template `granularity/prompt.md` and appending the graph to it.
Keep `prompt.md` itself unchanged: it is the template shared by all applications.

### Stage 4 – Deployment Planner

```bash
cd deployment
python deployment_planner.py                     # all applications, planned by priority
python deployment_planner.py smart_surveillance  # a single application
```

The planner reads the outputs of `resource_estimation/` and `offloadability/`
together with `infrastructure.json` and `sla_policy.json`, and writes one
deployment descriptor per application in `deployment/output/`. Each descriptor
contains the placement and replicas of every unit, the objective score *J*
(lower is better), the SLA compliance, node and link utilization, a
per-unit decision rationale, and the scores of the baselines (all-local,
cloud-only, greedy first-fit).

Search: exhaustive over the constraint-pruned candidate space when it has at
most `max_exhaustive_candidates` configurations (default 200,000), greedy +
local search otherwise.

### RQ2 – Scalability benchmark

Run the reproducible synthetic benchmark from the project root:

```bash
python -m pip install -r experiments/requirements.txt
python experiments/rq2_scalability_benchmark.py
```

The default run tests the 12 combinations of 2–5 movable units and 8, 16 or 24
Edge nodes with both exhaustive search and the planner's greedy+local-search
fallback. For each small case, a fixed seed is advanced deterministically until
the candidate space fits the exact-search limit. It also
tests `(m, N)` sizes `(10, 32)`, `(20, 64)` and `(40, 100)` using the fallback
only. Each case is repeated three times. A fixed random seed and generated
instances are saved for reproducibility. Results, including runtime samples,
candidate-space sizes, feasibility and small-case optimality gaps, are written
to `experiments/output/rq2_scalability/`. PDF plots are written to
`experiments/figures/`.

Use `--m-values`, `--n-values`, `--large-pairs`, `--repetitions` or
`--max-exact-configurations` to adjust the run. Use `--plot-only` to regenerate
the plots from saved results without rerunning the planner. Search evaluation
counts include greedy initialization and local-search scoring; wall-clock time
covers the complete `plan_app` call, including candidate generation, search,
baselines and replication.

### Stage 5 – Validation

```bash
cd validation
python deployment_validator.py               # validate the current plans
python deployment_validator.py --self-test   # inject faults and measure the detection rate
```

The validator re-derives every constraint (V1–V12 per application, J1–J3 on the
shared infrastructure) from the original contracts, without reusing the
planner's code. Each plan is reported as **Valid** or **Invalid**, with errors
(hard constraints) and warnings (soft constraints).

**Feedback loop.** When a plan is invalid, the validator writes
`deployment/feedback.json` with the nodes each violating unit must avoid. Re-run
the planner, which excludes these nodes, then validate again:

```bash
cd deployment && python deployment_planner.py
cd ../validation && python deployment_validator.py
```

## Configuration

- `deployment/infrastructure.json`: nodes (tier, site, CPU, memory, GPU memory,
  storage, availability, cost), links (bandwidth, latency) and, per application,
  the `anchors` (which device each non-offloadable unit is bound to) and the
  `original_host` of each unit.
- `deployment/sla_policy.json`: utilization target (default 0.8),
  provenance-based safety margins, availability mode (soft/hard), strict
  assumptions, replication policy and semantics, objective weights and
  normalization, and per-application priority, availability target and replicas.

## Citation

If you use this work, please cite the associated paper (reference to be added).
