You are an expert in IoT systems, Edge/Cloud computing, performance engineering and capacity planning. You act as the **Resource Estimation** stage of a pre-deployment offloading pipeline:

```
functional graph -> granularity analysis -> [RESOURCE ESTIMATION] -> offloadability analysis -> deployment planner
```

## Your task

You receive:

1. The **functional graph** of an IoT application (components and their functions).
2. The **granularity analysis result**: the execution units, their characteristics and the unit graph.

Both are given and correct. For EVERY execution unit, characterise the resources that ONE instance of the unit needs: CPU, memory, GPU, storage and network. Also characterise every edge of the unit graph.

- Do NOT change, merge or split execution units.
- Do NOT decide placement or offloadability. Never write "Edge", "Cloud", "should stay on the device", "should be offloaded", "offloadable", or name a node or tier as a destination.
- Use ONLY facts stated in the input. Where a value depends on something the input does not state (e.g. video resolution, number of users), make an explicit assumption and list it.

## Scope of this stage

| Stage | Question |
|---|---|
| Granularity | What should be grouped together? (done) |
| **Resource Estimation (you)** | How much CPU, GPU, memory, storage and network does each unit need? |
| Offloadability | Can each unit run remotely, and under which constraints? |
| Deployment Planner | Where does each unit run, with how many replicas? |

## Evidence hierarchy (most important rule)

Your estimates are **heuristic**, not measurements. Every resource must be built in this order, and each step must be visible in the output:

1. **Observed facts**: what the input explicitly states (component functions, named models, sensors, rates, platforms such as "Android app", "Arduino Uno", "Streamlit").
2. **Inferred characteristics**: what follows from those facts (e.g. "runs a video classification model on 16-frame clips").
3. **Level** (`very_low` ... `very_high`): the primary result. It must be justified by steps 1 and 2.
4. **Numerical estimate**: a coarse, secondary value derived from the level and your assumptions.
5. **Confidence**: how strongly the input supports steps 3 and 4.

The level is what later stages rely on. Numbers only refine it and must never look more precise than the evidence allows.

## Units, precision and reference hardware

| Resource | Unit | Reference |
|---|---|---|
| CPU | vCPU cores | one general-purpose x86-64 core at about 2.5-3 GHz |
| Memory | GB of RAM | working memory of the unit's own logic and data (see platform baselines) |
| GPU | `none`, `optional`, `required` + GB of GPU memory | a mid-range data-centre or embedded GPU |
| Storage | GB | local disk needed by one instance (models, buffers, logs) |
| Network | Mbps | sustained traffic in and out of one instance |

Precision rules: every CPU, memory, GPU-memory and storage number MUST be one of the values of this **estimation grid** (choose the closest). The grid makes it explicit that these numbers are coarse, order-of-magnitude estimates:

| Resource | Allowed values |
|---|---|
| CPU (cores) | 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16 |
| Memory (GB) | 0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32 |
| GPU memory (GB) | 0, 1, 2, 4, 8, 16, 24 |
| Storage (GB) | 0, 0.001, 0.01, 0.1, 0.5, 1, 2, 5, 10, 20, 50, 100 |

- Values below the smallest grid value are reported as that smallest value with level `very_low`, EXCEPT in the microcontroller case below.
- **Microcontrollers and other non-comparable platforms** (e.g. Arduino Uno firmware): do NOT express CPU or memory in x86 cores or GB. Set `typical_*` and `peak_*` to `null`, keep the level, and give the reason in `not_comparable_reason`. Only if the input states the real figure (e.g. a buffer size in bytes) may you report it in `native_estimate` with its own unit; otherwise `native_estimate` is `null`. Never invent a value such as 0.001 GB.
- **Network values are NOT gridded and have NO reporting floor.** `message_size_kb` is an estimate with at most 2 significant digits; `message_rate_per_s` comes from the input or a stated assumption; `bandwidth_mbps` is the exact result of the formula (up to 6 significant digits). A flow of 20 bytes per second is reported as 0.00016 Mbps, not rounded up. The Deployment Planner sums and compares link loads, so rounding would distort them.
- Set any other number to `null` (keep the level) when it is not meaningful, and say why in `basis`.
- If a unit contains a GPU-accelerable model, give the CPU estimate **with** the GPU and explain in `basis` how the need grows without it.

Levels, relative to these thresholds (applied to the `typical` value):

| Level | CPU (cores) | Memory (GB) | Storage (GB) | Network (Mbps) |
|---|---|---|---|---|
| `very_low` | < 0.1 | < 0.1 | < 0.1 | < 0.1 |
| `low` | 0.1 - 0.5 | 0.1 - 0.5 | 0.1 - 1 | 0.1 - 1 |
| `medium` | 0.5 - 2 | 0.5 - 2 | 1 - 10 | 1 - 10 |
| `high` | 2 - 4 | 2 - 8 | 10 - 50 | 10 - 100 |
| `very_high` | > 4 | > 8 | > 50 | > 100 |

## Application demand vs platform baseline

Separate what the unit's own logic needs from the overhead of the runtime it currently executes in (Android app process, Python interpreter, browser UI framework, microcontroller firmware, ...):

- `cpu` and `memory` in each unit profile = **application demand only** (the unit's logic, models, buffers and state).
- Runtime overhead goes in `platform_baselines`, ONCE per platform, listing all units that currently share it. Never attribute a shared runtime baseline to a single unit.
- The platform of each unit is a fact taken from the input (e.g. "In the Android app, ..."). Use `unknown` if the input does not say. Recording it is not a placement decision.

## Constraints carried from granularity

Copy into each profile, unchanged, the constraint information of the unit from the granularity result: `execution_constraint`, `deployment_role`, and the characteristics tags that express a binding (`hardware_access`, `user_interaction`, `external_service_dependency`). Also list the concrete hardware or platform the unit's components depend on, as stated in the input (e.g. "DHT22 sensor", "HC-05 Bluetooth module", "local webcam", "local speaker", "Android Bluetooth API"). This does not decide anything: it makes sure the constraints travel next to the numbers, so that a small resource demand is never read without its binding.

## Provenance of every estimate

Every resource estimate and every edge value carries a `provenance` label, so that later stages never treat a guess like a stated requirement:

| Provenance | Meaning | Example |
|---|---|---|
| `observed` | The value, or the fact that fixes it, is stated in the input. | "one measurement line every second" -> message rate 1/s |
| `inferred` | Derived by reasoning from stated facts, without extra assumptions. | "runs YOLOv8-large" -> GPU memory in the order of a few GB |
| `assumed` | Depends on an assumption you introduced. List those assumptions in `assumption_refs` (exact text from `assumptions`). | "input video is 1280x720 at 30 FPS" -> frame size and bandwidth |
| `unknown` | The input gives no basis at all. The level is `unknown` and the numbers are `null`. | a data rate that is neither stated nor reasonably assumable |

Rules:

- When several facts contribute, use the WEAKEST one, in the order `observed` > `inferred` > `assumed` > `unknown`.
- For an edge, `message_size_kb` and `message_rate_per_s` each have their own provenance, and `bandwidth_provenance` is the weaker of the two.
- `unknown` is preferred to an invented value. Never pick a number just to fill a field.
- The unit's overall `confidence` must be consistent with its provenances: `high` only if its main resources are `observed` or `inferred`, and `low` if most are `assumed` or `unknown`.

## Initialization units

For a unit with `unit_type` = `initialization` (e.g. a model loader):

- Its profile describes ONLY the initialization phase (downloading, reading, loading). `workload_pattern` = `startup_only` and `transient` = true when those resources are released after initialization.
- Give `startup_duration_s`: an estimated duration of the initialization phase (with an assumption), or `null` if there is no basis.
- Resources that stay in use after initialization belong to the units that use them. Example: models loaded by U4 and then used by U5 occupy memory in **U5's** profile (and GPU memory in U5's `gpu`), not in U4's. Never count the same memory or storage in both.
- Storage: if the initialization unit downloads artifacts (e.g. model files) that must stay on disk, report their size in its `storage` with `persistent` = true. The consuming units then do not count that storage again.
- Its outgoing edges are `startup_only`: `message_rate_per_s` = 0, `bandwidth_mbps` = 0, `latency_sensitivity` = `not_applicable`, and the one-time volume goes in `one_time_transfer_mb` (e.g. the size of the model loaded for the target unit).

## Communication edges

For every edge of the unit graph:

- Describe only what travels along **this hop**, in the direction of the edge (`source` -> `target`).
- `flow_path` is ALWAYS filled and follows these rules:
  - it starts at the unit where the payload is produced and ends at the unit that finally consumes it;
  - every consecutive pair in it is an edge of the granularity `unit_graph`, in the same direction;
  - it contains `source`, `target` as a consecutive pair;
  - if the payload is produced by `source` and consumed by `target`, it is simply `[source, target]`.

  Example: a farmer's command typed in U6 and relayed U6 -> U4 -> U3 -> U2 gives `flow_path` = `["U6", "U4", "U3", "U2"]` on each of the three edges. Do not add units that are not on the relay chain, and do not include component ids.
- `current_mechanism`: how the two units communicate TODAY, as stated or directly implied by the input: `in_process_call` (function call in the same program), `in_process_queue` (queue, buffer or shared variable between threads of the same program), `local_ipc` (between processes on the same machine), `bluetooth_serial`, `ip_network`, `local_hardware_bus` (e.g. a sensor wired to a microcontroller pin), `unknown`. Do not choose a mechanism the input does not support.
- `boundary`: distinguish logical from physical communication.
  - `logical`: the two units currently run in the same program or on the same machine (`in_process_call`, `in_process_queue`, `local_ipc`). Today this traffic crosses no network. It would become network traffic ONLY if the Deployment Planner separates the two units.
  - `physical`: the traffic already crosses a link between two separate physical devices or machines (`bluetooth_serial`, `ip_network`).
  - `hardware`: the traffic is a local hardware interface (`local_hardware_bus`). It cannot become network traffic.
  - `unknown`: the input does not say.
- `bandwidth_mbps` is ALWAYS the volume of the flow itself, whatever the boundary. For a `logical` edge it therefore means "the network load this flow would create if the two units were separated".
- `latency_sensitivity` describes the **flow**, not the unit. Levels:
  - `high`: the data must arrive within the processing of the current input (e.g. each video frame, each real-time alert); a delay directly degrades the application output.
  - `medium`: seconds-scale timeliness (e.g. a dashboard refreshed every second, an operator command).
  - `low`: no timeliness requirement beyond eventual delivery (e.g. log records, historical storage).
  - `not_applicable`: `startup_only` flows (initialization transfers).
  - `unknown`: the input gives no basis for any of the above.

  Start from the level in the granularity `unit_graph` and refine it only when the input supports it. Always give a `reason` that cites the evidence (e.g. "frames are sent on every processed frame"). `unknown` must use the reason "No explicit latency requirement in the input".

## Output format

Reply with ONE JSON object only, inside a single ```json code block, with no text before or after it. Do not create a file, canvas or artifact.

```json
{
  "application_id": "<copy from input>",
  "estimation_method": "heuristic_llm",
  "assumptions": ["<global assumption, e.g. input video is 1280x720 at 30 FPS>"],
  "platform_baselines": [
    {
      "platform": "<e.g. Android app process>",
      "units": ["<unit ids currently running on this platform>"],
      "cpu_cores": 0.0,
      "memory_gb": 0.0,
      "basis": "<what the baseline consists of>",
      "confidence": "low | medium | high"
    }
  ],
  "resource_profiles": [
    {
      "unit_id": "U1",
      "name": "<copy from granularity>",
      "unit_type": "<copy from granularity>",
      "platform": "<from input, or unknown>",
      "workload_pattern": "continuous | periodic | event_driven | startup_only",
      "constraints": {
        "execution_constraint": "<copy from granularity>",
        "deployment_role": "<copy from granularity>",
        "binding_characteristics": ["<hardware_access | user_interaction | external_service_dependency, copied from granularity>"],
        "required_hardware_or_platform": ["<concrete hardware / platform stated in the input>"]
      },
      "evidence": {
        "observed_facts": ["<facts quoted or paraphrased from the input>"],
        "inferred_characteristics": ["<what follows from the facts>"]
      },
      "cpu": {
        "level": "very_low | low | medium | high | very_high | unknown",
        "provenance": "observed | inferred | assumed | unknown",
        "assumption_refs": ["<assumptions this value depends on, if provenance = assumed>"],
        "typical_cores": 0.0,
        "peak_cores": 0.0,
        "native_estimate": null,
        "not_comparable_reason": null,
        "basis": "<which operations drive the CPU need>"
      },
      "memory": {
        "level": "very_low | low | medium | high | very_high | unknown",
        "provenance": "observed | inferred | assumed | unknown",
        "assumption_refs": ["<assumptions this value depends on, if provenance = assumed>"],
        "typical_gb": 0.0,
        "peak_gb": 0.0,
        "native_estimate": null,
        "not_comparable_reason": null,
        "basis": "<models, buffers, state of the unit itself>"
      },
      "gpu": {
        "requirement": "none | optional | required | unknown",
        "provenance": "observed | inferred | assumed | unknown",
        "assumption_refs": [],
        "memory_gb": 0.0,
        "basis": "<why>"
      },
      "storage": {
        "level": "very_low | low | medium | high | very_high | unknown",
        "provenance": "observed | inferred | assumed | unknown",
        "assumption_refs": ["<assumptions this value depends on, if provenance = assumed>"],
        "size_gb": 0.0,
        "persistent": false,
        "growth": "none | bounded | grows_over_time",
        "basis": "<what is stored>"
      },
      "network": {
        "level": "very_low | low | medium | high | very_high | unknown",
        "provenance": "observed | inferred | assumed | unknown",
        "assumption_refs": ["<assumptions this value depends on, if provenance = assumed>"],
        "physical_ingress_mbps": 0.0,
        "physical_egress_mbps": 0.0,
        "potential_ingress_mbps": 0.0,
        "potential_egress_mbps": 0.0,
        "basis": "<which unit-graph edges produce this traffic>"
      },
      "transient": false,
      "startup_duration_s": null,
      "confidence": "low | medium | high",
      "assumptions": ["<unit-specific assumption>"],
      "how_to_measure": "<how this estimate could be validated on the real application, e.g. 'profile CPU and RSS of the inference thread with psutil and GPU memory with nvidia-smi while processing a 30 FPS video'>"
    }
  ],
  "communication_requirements": [
    {
      "source": "U1",
      "target": "U2",
      "payload": "<what travels along this hop>",
      "flow_path": ["<unit ids from origin to final consumer, if the payload is relayed>"],
      "current_mechanism": "in_process_call | in_process_queue | local_ipc | bluetooth_serial | ip_network | local_hardware_bus | unknown",
      "boundary": "logical | physical | hardware | unknown",
      "message_size_kb": 0.0,
      "message_size_provenance": "observed | inferred | assumed | unknown",
      "message_rate_per_s": 0.0,
      "message_rate_provenance": "observed | inferred | assumed | unknown",
      "bandwidth_provenance": "<weaker of the two>",
      "assumption_refs": ["<assumptions this edge depends on>"],
      "bandwidth_mbps": 0.0,
      "one_time_transfer_mb": null,
      "latency_sensitivity": {
        "level": "low | medium | high | not_applicable | unknown",
        "reason": "<evidence, or 'No explicit latency requirement in the input'>"
      },
      "basis": "<how the values were derived>"
    }
  ],
  "summary": {
    "number_of_units": 0,
    "current_platform_load": [
      {
        "platform": "<platform>",
        "runtime_units": ["<runtime units currently on this platform>"],
        "application_cores": 0.0,
        "application_memory_gb": 0.0,
        "baseline_cores": 0.0,
        "baseline_memory_gb": 0.0,
        "combined_cores": 0.0,
        "combined_memory_gb": 0.0,
        "storage_gb": 0.0,
        "units_without_numeric_values": ["<unit ids whose values are null>"],
        "provenance": "<weakest provenance of the values summed>"
      }
    ],
    "initialization_demand": {
      "units": ["<initialization units>"],
      "peak_cores": 0.0,
      "peak_memory_gb": 0.0,
      "persistent_storage_gb": 0.0,
      "startup_duration_s": null
    },
    "units_requiring_gpu": ["<unit ids with gpu.requirement = required>"],
    "physical_boundaries": ["<edges source->target with boundary = physical, and their mechanism>"],
    "provenance_overview": {
      "estimates_by_provenance": {"observed": 0, "inferred": 0, "assumed": 0, "unknown": 0},
      "edges_by_bandwidth_provenance": {"observed": 0, "inferred": 0, "assumed": 0, "unknown": 0},
      "key_assumptions": ["<the few assumptions most estimates depend on>"]
    },
    "resource_observations": ["<short factual observations, e.g. 'All units have very low computational demand.'>"]
  },
  "calibration_status": "uncalibrated"
}
```

## Rules for the output

- One entry in `resource_profiles` per execution unit, same `unit_id`s, same order, none added or missing.
- One entry in `communication_requirements` per edge of the granularity `unit_graph`, same source and target, in the same direction.
- `bandwidth_mbps` = `message_size_kb` x `message_rate_per_s` x 8 / 1000, exact (up to 6 significant digits, no grid, no floor). For `startup_only` flows see "Initialization units": rate 0, bandwidth 0, volume in `one_time_transfer_mb`. For all other flows `one_time_transfer_mb` is `null`.
- A unit's `potential_ingress_mbps` / `potential_egress_mbps` = exact sum of `bandwidth_mbps` over ALL its incoming / outgoing edges except `hardware` edges (the load if every unit were separated). `physical_ingress_mbps` / `physical_egress_mbps` = exact sum over its `physical` edges only (the load that already crosses a device link today). The network `level` is based on the potential values.
- All numbers are for ONE instance. Do not multiply by replicas.
- **No global total across platforms.** Summing cores of a microcontroller, a phone and a server is meaningless.
- `current_platform_load` describes the load of the application **as it runs today**, one entry per platform in `platform_baselines`. It is NOT a capacity requirement for any future node, because the Deployment Planner may separate these units.
  - `application_*` = sum of the `typical` application values of the RUNTIME units currently on that platform. Units with `null` values are skipped and listed in `units_without_numeric_values`.
  - `baseline_*` = the values of that platform's entry in `platform_baselines`.
  - `combined_*` = `application_*` + `baseline_*`, i.e. the estimated total load if nothing is moved.
  - `storage_gb` = sum of `size_gb` of those units.
  - For a non-comparable platform (e.g. a microcontroller), all numeric fields are `null`.
- Initialization units never appear in `current_platform_load`; they are reported once in `initialization_demand` (peak values, persistent storage, duration).
- No ranking or "dominant unit" field. Factual interpretations go in `resource_observations` (e.g. "U5 and U6 account for most of the estimated application CPU demand; all other runtime units are very_low").
- `physical_boundaries` lists every edge whose `boundary` is `physical`.
- `calibration_status` is always `uncalibrated`: the values are LLM heuristics until they are compared with measurements.
- `transient` = true only for `initialization` units whose resources are released after initialization. `startup_duration_s` is `null` for runtime units.
- `confidence`: `high` when the input names the model, sensor or data rate; `medium` when the estimate follows from the described function; `low` when it relies mainly on assumptions.
- No placement recommendation and no offloadability statement anywhere.

Before answering, check that every unit and every unit-graph edge has exactly one entry, that every estimate has a provenance and every `assumed` value cites its assumptions, that `unknown` values have null numbers, that `provenance_overview` counts match (one estimate = one of cpu, memory, gpu, storage, network per unit), that each level matches its `typical` value, that CPU/memory/storage numbers are grid values, that network numbers are exact and unfloored, that no GB or core value was given for a microcontroller, that every edge has a boundary and a valid `flow_path`, that no memory or storage is counted both in an initialization unit and in the unit that uses it, that `combined_*` = `application_*` + `baseline_*`, that the constraints were copied unchanged, that no platform baseline is counted inside a unit, that the bandwidth arithmetic is exact and the physical/potential sums match the edges and that the summary totals add up.

## Input

```json
{
  "application_id": "smart_surveillance",
  "functional_graph": {
    "application_id": "smart_surveillance",
    "nodes": [
      {
        "id": "user_interface",
        "name": "User Interface",
        "function": "Streamlit dashboard where the operator selects the video source (webcam or uploaded file), sets frame-skip, resolution and alert options, and starts or stops detection"
      },
      {
        "id": "video_acquisition",
        "name": "Video Acquisition",
        "function": "Captures frames continuously from the local webcam or reads them from an uploaded video file at the target FPS"
      },
      {
        "id": "frame_preprocessing",
        "name": "Frame Preprocessing",
        "function": "Resizes frames to the selected display resolution, applies frame skipping, and produces 224x224 frames for action recognition"
      },
      {
        "id": "frame_buffering",
        "name": "Frame Buffering",
        "function": "Keeps a sliding buffer of the last 16 sampled frames used as the input clip for crime detection"
      },
      {
        "id": "model_loader",
        "name": "Model Loader",
        "function": "Downloads pretrained models from Hugging Face and PyTorchVideo (YOLOv8-large, VideoMAE crime detector, I3D-R50) and loads them into CPU/GPU memory at startup"
      },
      {
        "id": "object_detection",
        "name": "Object Detection",
        "function": "Runs YOLOv8-large deep learning inference on each sent frame to detect objects and people with confidence above 0.5"
      },
      {
        "id": "object_tracking",
        "name": "Object Tracking",
        "function": "Applies DeepSORT tracking with a MobileNet appearance embedder to assign persistent IDs to detections and draws labeled bounding boxes on the frame"
      },
      {
        "id": "crime_detection",
        "name": "Crime Detection",
        "function": "Runs a VideoMAE video classification model on the 16-frame clip to classify the scene as crime or no crime"
      },
      {
        "id": "activity_recognition",
        "name": "Normal Activity Recognition",
        "function": "When no crime is detected, runs the pretrained I3D-R50 model (Kinetics-400) on the same clip to label the ongoing normal activity"
      },
      {
        "id": "alert_notification",
        "name": "Alert Notification",
        "function": "Raises a real-time alert when a crime is detected: status message and optional beep on the local machine speaker"
      },
      {
        "id": "video_display",
        "name": "Video Display",
        "function": "Renders the annotated frames, the current detection status and FPS statistics in the user interface"
      },
      {
        "id": "event_logging",
        "name": "Event Logging",
        "function": "Writes timestamped detection results, crime events and system events to log files in the logs folder"
      }
    ],
    "edges": [
      {
        "source": "user_interface",
        "target": "video_acquisition",
        "type": "control_flow"
      },
      {
        "source": "user_interface",
        "target": "alert_notification",
        "type": "control_flow"
      },
      {
        "source": "video_acquisition",
        "target": "frame_preprocessing",
        "type": "data_flow"
      },
      {
        "source": "frame_preprocessing",
        "target": "object_detection",
        "type": "data_flow"
      },
      {
        "source": "frame_preprocessing",
        "target": "frame_buffering",
        "type": "data_flow"
      },
      {
        "source": "frame_preprocessing",
        "target": "video_display",
        "type": "data_flow"
      },
      {
        "source": "model_loader",
        "target": "object_detection",
        "type": "dependency"
      },
      {
        "source": "model_loader",
        "target": "crime_detection",
        "type": "dependency"
      },
      {
        "source": "model_loader",
        "target": "activity_recognition",
        "type": "dependency"
      },
      {
        "source": "object_detection",
        "target": "object_tracking",
        "type": "data_flow"
      },
      {
        "source": "object_tracking",
        "target": "video_display",
        "type": "data_flow"
      },
      {
        "source": "frame_buffering",
        "target": "crime_detection",
        "type": "data_flow"
      },
      {
        "source": "crime_detection",
        "target": "activity_recognition",
        "type": "control_flow"
      },
      {
        "source": "crime_detection",
        "target": "alert_notification",
        "type": "event"
      },
      {
        "source": "crime_detection",
        "target": "video_display",
        "type": "data_flow"
      },
      {
        "source": "crime_detection",
        "target": "event_logging",
        "type": "data_flow"
      },
      {
        "source": "activity_recognition",
        "target": "video_display",
        "type": "data_flow"
      },
      {
        "source": "activity_recognition",
        "target": "event_logging",
        "type": "data_flow"
      }
    ]
  },
  "granularity": {
    "application_id": "smart_surveillance",
    "granularity": {
      "level": "task",
      "justification": "The graph contains clearly identifiable functional stages with heterogeneous execution constraints and characteristics. Operator I/O (Streamlit dashboard, display, speaker alert) and camera acquisition both require local hardware or the local operator interface. The other stages are frame preprocessing, two distinct deep-learning pipelines (per-frame YOLOv8-large detection with DeepSORT tracking, and clip-based VideoMAE crime detection with conditional I3D-R50 activity recognition), a startup-time model loader and event logging to files. Coupling is strong inside each stage: detection feeds tracking on each frame, and the 16-frame buffer feeds crime detection, which gates activity recognition on the same clip. Coupling between stages is weaker or of a different nature (control flows, events, classification results, startup dependencies). Task-level units separate the hardware- and interface-bound stages from the ML inference pipelines, so the later stages can assess each stage independently.",
      "alternatives": [
        {
          "level": "application",
          "rejected_because": "A single unit would merge the per-frame detection/tracking pipeline, the clip-based crime/activity pipeline, preprocessing, the startup-time model loader and logging. These have different characteristics: two separate ML inference pipelines with different inputs (single frames vs. 16-frame clips) and triggers, a stage that runs only at startup, and a stage that writes persistent log files. Several inter-stage flows carry only control signals, events or classification results, so coupling is not uniformly intensive across the graph, and a single unit would remove flexibility without a matching communication benefit."
        },
        {
          "level": "method",
          "rejected_because": "One unit per node would cut the tightest links in the graph. Object detection passes detections for each frame to tracking, and the sliding frame buffer supplies 16-frame clips to crime detection, which gates activity recognition on the same clip. Splitting them would add network hops on the real-time path and duplicate frame transfers, without any benefit from independent handling, because these components must execute together to produce each result."
        }
      ]
    },
    "execution_units": [
      {
        "unit_id": "U1",
        "name": "Operator Interface",
        "components": [
          "user_interface",
          "video_display",
          "alert_notification"
        ],
        "unit_type": "runtime",
        "rationale": "These components form the operator I/O stage: the Streamlit dashboard for source selection and detection control, the rendering of annotated frames, detection status and FPS statistics, and the real-time status message with optional beep on the local machine speaker. They require direct access to the local operator interface and audio hardware, so they are grouped together and kept separate from components with different execution characteristics.",
        "grouping_criteria": [
          "device_binding",
          "cohesion",
          "latency"
        ],
        "cohesion": "medium",
        "communication_intensity_with_other_units": "high",
        "internal_dependencies": [
          "user_interface -> alert_notification"
        ],
        "external_dependencies": [
          "user_interface -> video_acquisition",
          "frame_preprocessing -> video_display",
          "object_tracking -> video_display",
          "crime_detection -> alert_notification",
          "crime_detection -> video_display",
          "activity_recognition -> video_display"
        ],
        "execution_constraint": "device_bound",
        "characteristics": [
          "hardware_access",
          "user_interaction",
          "high_frequency_input",
          "latency_sensitive",
          "event_driven"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U2",
        "name": "Video Acquisition",
        "components": [
          "video_acquisition"
        ],
        "unit_type": "runtime",
        "rationale": "Video Acquisition captures frames continuously from the local webcam, or reads an uploaded video file, at the target FPS. It requires direct access to the local camera, a requirement that no other component shares, so it forms its own unit and is kept separate from components with different execution characteristics.",
        "grouping_criteria": [
          "device_binding",
          "independence"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "high",
        "internal_dependencies": [],
        "external_dependencies": [
          "user_interface -> video_acquisition",
          "video_acquisition -> frame_preprocessing"
        ],
        "execution_constraint": "device_bound",
        "characteristics": [
          "hardware_access",
          "high_frequency_input",
          "latency_sensitive"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U3",
        "name": "Frame Preprocessing",
        "components": [
          "frame_preprocessing"
        ],
        "unit_type": "runtime",
        "rationale": "Frame Preprocessing is a distinct stage that resizes frames to the display resolution, applies frame skipping and produces 224x224 frames. It fans out to three consumers: object detection, the crime-detection frame buffer and the display. It does not require local hardware or the operator interface, so it is not grouped with acquisition. It is also kept out of either inference pipeline because it serves both pipelines and the display.",
        "grouping_criteria": [
          "cohesion",
          "independence",
          "device_binding"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "high",
        "internal_dependencies": [],
        "external_dependencies": [
          "video_acquisition -> frame_preprocessing",
          "frame_preprocessing -> object_detection",
          "frame_preprocessing -> frame_buffering",
          "frame_preprocessing -> video_display"
        ],
        "execution_constraint": "flexible",
        "characteristics": [
          "high_frequency_input",
          "latency_sensitive"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U4",
        "name": "Model Provisioning",
        "components": [
          "model_loader"
        ],
        "unit_type": "initialization",
        "rationale": "Model Loader downloads the pretrained YOLOv8-large, VideoMAE and I3D-R50 models from Hugging Face and PyTorchVideo and loads them at startup. It has no runtime data flow, only dependency edges to three inference components that belong to two different pipelines. It is kept as its own unit because merging it into either pipeline would misrepresent the other pipeline's dependency. It prepares both inference units rather than processing inputs itself.",
        "grouping_criteria": [
          "independence",
          "cohesion"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [],
        "external_dependencies": [
          "model_loader -> object_detection",
          "model_loader -> crime_detection",
          "model_loader -> activity_recognition"
        ],
        "execution_constraint": "flexible",
        "characteristics": [
          "external_service_dependency"
        ],
        "deployment_role": "dependency",
        "supports": [
          "U5",
          "U6"
        ]
      },
      {
        "unit_id": "U5",
        "name": "Object Detection and Tracking",
        "components": [
          "object_detection",
          "object_tracking"
        ],
        "unit_type": "runtime",
        "rationale": "YOLOv8-large detection and DeepSORT tracking form one coherent per-frame perception pipeline. object_detection feeds object_tracking on every processed frame, and the tracker assigns persistent IDs and draws labeled bounding boxes. They are grouped to avoid a network hop per frame on the path to the display.",
        "grouping_criteria": [
          "cohesion",
          "coupling",
          "latency"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "high",
        "internal_dependencies": [
          "object_detection -> object_tracking"
        ],
        "external_dependencies": [
          "frame_preprocessing -> object_detection",
          "model_loader -> object_detection",
          "object_tracking -> video_display"
        ],
        "execution_constraint": "flexible",
        "characteristics": [
          "ml_inference",
          "high_frequency_input",
          "latency_sensitive",
          "stateful"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U6",
        "name": "Crime and Activity Recognition",
        "components": [
          "frame_buffering",
          "crime_detection",
          "activity_recognition"
        ],
        "unit_type": "runtime",
        "rationale": "The sliding 16-frame buffer, VideoMAE crime classification and I3D-R50 activity recognition form one coherent clip-based video understanding stage. The buffer produces the clip consumed by crime detection, and activity recognition runs on that same clip only when crime detection reports no crime. Keeping them together avoids transferring the clip across the network twice and keeps the conditional control flow internal.",
        "grouping_criteria": [
          "cohesion",
          "coupling",
          "latency"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "medium",
        "internal_dependencies": [
          "frame_buffering -> crime_detection",
          "crime_detection -> activity_recognition"
        ],
        "external_dependencies": [
          "frame_preprocessing -> frame_buffering",
          "model_loader -> crime_detection",
          "model_loader -> activity_recognition",
          "crime_detection -> alert_notification",
          "crime_detection -> video_display",
          "crime_detection -> event_logging",
          "activity_recognition -> video_display",
          "activity_recognition -> event_logging"
        ],
        "execution_constraint": "flexible",
        "characteristics": [
          "ml_inference",
          "high_frequency_input",
          "latency_sensitive",
          "stateful",
          "event_driven"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U7",
        "name": "Event Logging",
        "components": [
          "event_logging"
        ],
        "unit_type": "runtime",
        "rationale": "Event Logging writes timestamped detection results, crime events and system events to log files. It is a storage stage whose scaling and durability needs differ from the inference stages, so it is kept separate.",
        "grouping_criteria": [
          "scalability",
          "independence"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [],
        "external_dependencies": [
          "crime_detection -> event_logging",
          "activity_recognition -> event_logging"
        ],
        "execution_constraint": "flexible",
        "characteristics": [
          "persistent_storage",
          "event_driven"
        ],
        "deployment_role": "service",
        "supports": []
      }
    ],
    "unit_graph": {
      "nodes": [
        "U1",
        "U2",
        "U3",
        "U4",
        "U5",
        "U6",
        "U7"
      ],
      "edges": [
        {
          "source": "U1",
          "target": "U2",
          "component_edges": [
            "user_interface -> video_acquisition"
          ],
          "types": [
            "control_flow"
          ],
          "data_characteristics": {
            "frequency": "event_driven",
            "volume": "low",
            "latency_sensitivity": "unknown"
          }
        },
        {
          "source": "U2",
          "target": "U3",
          "component_edges": [
            "video_acquisition -> frame_preprocessing"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "continuous",
            "volume": "high",
            "latency_sensitivity": "high"
          }
        },
        {
          "source": "U3",
          "target": "U1",
          "component_edges": [
            "frame_preprocessing -> video_display"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "continuous",
            "volume": "high",
            "latency_sensitivity": "high"
          }
        },
        {
          "source": "U3",
          "target": "U5",
          "component_edges": [
            "frame_preprocessing -> object_detection"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "continuous",
            "volume": "high",
            "latency_sensitivity": "high"
          }
        },
        {
          "source": "U3",
          "target": "U6",
          "component_edges": [
            "frame_preprocessing -> frame_buffering"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "continuous",
            "volume": "high",
            "latency_sensitivity": "high"
          }
        },
        {
          "source": "U4",
          "target": "U5",
          "component_edges": [
            "model_loader -> object_detection"
          ],
          "types": [
            "dependency"
          ],
          "data_characteristics": {
            "frequency": "startup_only",
            "volume": "unknown",
            "latency_sensitivity": "low"
          }
        },
        {
          "source": "U4",
          "target": "U6",
          "component_edges": [
            "model_loader -> crime_detection",
            "model_loader -> activity_recognition"
          ],
          "types": [
            "dependency"
          ],
          "data_characteristics": {
            "frequency": "startup_only",
            "volume": "unknown",
            "latency_sensitivity": "low"
          }
        },
        {
          "source": "U5",
          "target": "U1",
          "component_edges": [
            "object_tracking -> video_display"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "continuous",
            "volume": "high",
            "latency_sensitivity": "high"
          }
        },
        {
          "source": "U6",
          "target": "U1",
          "component_edges": [
            "crime_detection -> alert_notification",
            "crime_detection -> video_display",
            "activity_recognition -> video_display"
          ],
          "types": [
            "event",
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "continuous",
            "volume": "low",
            "latency_sensitivity": "high"
          }
        },
        {
          "source": "U6",
          "target": "U7",
          "component_edges": [
            "crime_detection -> event_logging",
            "activity_recognition -> event_logging"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "continuous",
            "volume": "low",
            "latency_sensitivity": "low"
          }
        }
      ]
    },
    "granularity_summary": {
      "number_of_components": 12,
      "number_of_execution_units": 7,
      "total_edges": 18,
      "internal_edges": 4,
      "cut_edges": 14,
      "overall_strategy": "Task-level granularity: operator I/O and camera acquisition, which require local hardware or the local operator interface, are separated from all other components, and each of the two ML inference pipelines (per-frame detection and tracking, clip-based crime and activity recognition) forms one cohesive runtime unit. Preprocessing and logging remain separate runtime stages, while model provisioning is an initialization dependency that prepares both inference units."
    }
  }
}
```
