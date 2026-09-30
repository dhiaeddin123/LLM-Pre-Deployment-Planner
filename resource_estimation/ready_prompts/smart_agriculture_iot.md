<!-- AUTO-GENERATED from prompt.md + input/smart_agriculture_iot.json. Copy ALL of this file into the LLM chat. Save the reply as output/smart_agriculture_iot.json. Do not edit. -->

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
  "application_id": "smart_agriculture_iot",
  "functional_graph": {
    "application_id": "smart_agriculture_iot",
    "nodes": [
      {
        "id": "temperature_humidity_sensing",
        "name": "Temperature and Humidity Sensing",
        "function": "Reads air temperature and humidity from a DHT22 sensor wired to the Arduino Uno sensor node, once per loop iteration (about every second)"
      },
      {
        "id": "soil_moisture_sensing",
        "name": "Soil Moisture Sensing",
        "function": "Reads the soil moisture level from an analog soil moisture sensor wired to the Arduino Uno sensor node, once per loop iteration"
      },
      {
        "id": "measurement_packaging",
        "name": "Measurement Packaging",
        "function": "On the Arduino Uno, formats the latest temperature, humidity and soil moisture values into one space-separated text line"
      },
      {
        "id": "sensor_command_handler",
        "name": "Sensor Command Handler",
        "function": "On the Arduino Uno, interprets single-character commands received over Bluetooth ('h', 't', 'm') and replies with the requested humidity, temperature or soil moisture value"
      },
      {
        "id": "sensor_bluetooth_link",
        "name": "Sensor Bluetooth Link",
        "function": "HC-05 Bluetooth module on the Arduino Uno (serial, 9600 baud): transmits one measurement line every second and receives commands from the mobile app"
      },
      {
        "id": "device_discovery",
        "name": "Device Discovery",
        "function": "In the Android app, lists bonded Bluetooth devices, discovers nearby devices and lets the farmer select the sensor node"
      },
      {
        "id": "app_bluetooth_connection",
        "name": "App Bluetooth Connection",
        "function": "In the Android app, opens a Bluetooth serial connection to the selected sensor node, receives its byte stream and sends outgoing commands"
      },
      {
        "id": "stream_parsing",
        "name": "Stream Parsing",
        "function": "In the Android app, removes backspace control characters from the received bytes, splits the stream into lines and each line into temperature, humidity and soil moisture values"
      },
      {
        "id": "measurement_aggregation",
        "name": "Measurement Aggregation",
        "function": "In the Android app, keeps a sliding window of the last 10 readings of each measurement and computes their mean values"
      },
      {
        "id": "dashboard_display",
        "name": "Dashboard Display",
        "function": "In the Android app, shows tiles with the mean temperature, humidity and soil moisture, plus a rainfall tile with a placeholder value"
      },
      {
        "id": "trend_chart",
        "name": "Temperature Trend Chart",
        "function": "In the Android app, draws a line chart of the temperature readings in the current sliding window"
      },
      {
        "id": "command_input",
        "name": "Command Input",
        "function": "In the Android app, text field where the farmer types a command that is sent to the sensor node"
      }
    ],
    "edges": [
      {
        "source": "temperature_humidity_sensing",
        "target": "measurement_packaging",
        "type": "data_flow"
      },
      {
        "source": "soil_moisture_sensing",
        "target": "measurement_packaging",
        "type": "data_flow"
      },
      {
        "source": "temperature_humidity_sensing",
        "target": "sensor_command_handler",
        "type": "data_flow"
      },
      {
        "source": "soil_moisture_sensing",
        "target": "sensor_command_handler",
        "type": "data_flow"
      },
      {
        "source": "measurement_packaging",
        "target": "sensor_bluetooth_link",
        "type": "data_flow"
      },
      {
        "source": "sensor_command_handler",
        "target": "sensor_bluetooth_link",
        "type": "data_flow"
      },
      {
        "source": "sensor_bluetooth_link",
        "target": "sensor_command_handler",
        "type": "control_flow"
      },
      {
        "source": "sensor_bluetooth_link",
        "target": "app_bluetooth_connection",
        "type": "data_flow"
      },
      {
        "source": "app_bluetooth_connection",
        "target": "sensor_bluetooth_link",
        "type": "control_flow"
      },
      {
        "source": "device_discovery",
        "target": "app_bluetooth_connection",
        "type": "control_flow"
      },
      {
        "source": "command_input",
        "target": "app_bluetooth_connection",
        "type": "data_flow"
      },
      {
        "source": "app_bluetooth_connection",
        "target": "stream_parsing",
        "type": "data_flow"
      },
      {
        "source": "stream_parsing",
        "target": "measurement_aggregation",
        "type": "data_flow"
      },
      {
        "source": "measurement_aggregation",
        "target": "dashboard_display",
        "type": "data_flow"
      },
      {
        "source": "measurement_aggregation",
        "target": "trend_chart",
        "type": "data_flow"
      }
    ]
  },
  "granularity": {
    "application_id": "smart_agriculture_iot",
    "granularity": {
      "level": "task",
      "justification": "The graph contains identifiable functional stages with heterogeneous execution constraints: environmental sensing (DHT22 and analog soil moisture sensor), sensor-side measurement formatting and command handling, the HC-05 Bluetooth link on the Arduino Uno, Bluetooth discovery and connection in the Android app, stream parsing with sliding-window aggregation, and the farmer-facing dashboard, chart and command input. Several stages require direct access to local hardware (sensors, HC-05 module, the app's Bluetooth connection) or to the local operator interface, while parsing and aggregation have neither requirement and keep sliding-window state. Coupling is strong inside each stage: parsing feeds aggregation on every received line, and device discovery drives the connection. Between stages, coupling consists of single text lines once per second, single-character commands and aggregated values. Task-level units keep the hardware- and interface-bound stages separate from the processing stages without fragmenting cohesive functions.",
      "alternatives": [
        {
          "level": "application",
          "rejected_because": "Grouping all components without a hardware or interface requirement into one unit would merge measurement packaging and command handling, which the graph describes as Arduino Uno functions, with stream parsing and aggregation, which the graph describes as Android app functions. These components are separated by the Bluetooth link and serve different functions (formatting and answering sensor-side requests vs. parsing and windowed averaging of the received stream). Coupling across the whole graph is not intensive, since the flows are one text line per second and occasional single-character commands, so a single unit would join weakly related components."
        },
        {
          "level": "method",
          "rejected_because": "The nodes are small functions that do not perform independent processing. Both sensing functions feed the same packaging and command-handling functions, parsing exists only to feed aggregation, and discovery exists only to set up the connection. One unit per node would split these tightly coupled pairs and add communication hops without any benefit from independent handling."
        }
      ]
    },
    "execution_units": [
      {
        "unit_id": "U1",
        "name": "Environmental Sensing",
        "components": [
          "temperature_humidity_sensing",
          "soil_moisture_sensing"
        ],
        "unit_type": "runtime",
        "rationale": "Both components read physical measurements from sensors wired to the Arduino Uno (DHT22 for air temperature and humidity, an analog sensor for soil moisture) once per loop iteration. They form one coherent sensing function and share the requirement of direct access to local sensor hardware, so they are grouped together and kept separate from components with different execution characteristics.",
        "grouping_criteria": [
          "device_binding",
          "cohesion"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [],
        "external_dependencies": [
          "temperature_humidity_sensing -> measurement_packaging",
          "soil_moisture_sensing -> measurement_packaging",
          "temperature_humidity_sensing -> sensor_command_handler",
          "soil_moisture_sensing -> sensor_command_handler"
        ],
        "execution_constraint": "device_bound",
        "characteristics": [
          "hardware_access"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U2",
        "name": "Sensor Data Formatting and Command Handling",
        "components": [
          "measurement_packaging",
          "sensor_command_handler"
        ],
        "unit_type": "runtime",
        "rationale": "Measurement Packaging formats the latest temperature, humidity and soil moisture values into one text line, and the Sensor Command Handler answers single-character requests ('h', 't', 'm') with the requested value. Both consume the same sensor readings and produce the outgoing messages for the Bluetooth link, forming one coherent sensor-side data handling function. Neither accesses hardware directly, so they are kept separate from the sensing and Bluetooth hardware stages.",
        "grouping_criteria": [
          "cohesion",
          "coupling",
          "device_binding"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [],
        "external_dependencies": [
          "temperature_humidity_sensing -> measurement_packaging",
          "soil_moisture_sensing -> measurement_packaging",
          "temperature_humidity_sensing -> sensor_command_handler",
          "soil_moisture_sensing -> sensor_command_handler",
          "measurement_packaging -> sensor_bluetooth_link",
          "sensor_command_handler -> sensor_bluetooth_link",
          "sensor_bluetooth_link -> sensor_command_handler"
        ],
        "execution_constraint": "flexible",
        "characteristics": [
          "event_driven"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U3",
        "name": "Sensor Bluetooth Link",
        "components": [
          "sensor_bluetooth_link"
        ],
        "unit_type": "runtime",
        "rationale": "The HC-05 Bluetooth module on the Arduino Uno transmits one measurement line every second and receives commands from the mobile app. It requires direct access to the local Bluetooth hardware and is the communication boundary between the sensor side and the Android app, so it forms its own unit and is kept separate from components with different execution characteristics.",
        "grouping_criteria": [
          "device_binding",
          "independence"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "medium",
        "internal_dependencies": [],
        "external_dependencies": [
          "measurement_packaging -> sensor_bluetooth_link",
          "sensor_command_handler -> sensor_bluetooth_link",
          "sensor_bluetooth_link -> sensor_command_handler",
          "sensor_bluetooth_link -> app_bluetooth_connection",
          "app_bluetooth_connection -> sensor_bluetooth_link"
        ],
        "execution_constraint": "device_bound",
        "characteristics": [
          "hardware_access"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U4",
        "name": "App Bluetooth Connectivity",
        "components": [
          "device_discovery",
          "app_bluetooth_connection"
        ],
        "unit_type": "runtime",
        "rationale": "Device Discovery lists bonded and nearby Bluetooth devices and lets the farmer select the sensor node, and App Bluetooth Connection opens the serial connection to that node, receives its byte stream and sends outgoing commands. Discovery exists only to establish the connection, so both form one coherent connectivity function. They share the requirement of direct access to the app's local Bluetooth hardware, so they are grouped together and kept separate from components with different execution characteristics.",
        "grouping_criteria": [
          "device_binding",
          "cohesion",
          "coupling"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "medium",
        "internal_dependencies": [
          "device_discovery -> app_bluetooth_connection"
        ],
        "external_dependencies": [
          "sensor_bluetooth_link -> app_bluetooth_connection",
          "app_bluetooth_connection -> sensor_bluetooth_link",
          "command_input -> app_bluetooth_connection",
          "app_bluetooth_connection -> stream_parsing"
        ],
        "execution_constraint": "device_bound",
        "characteristics": [
          "hardware_access",
          "user_interaction",
          "stateful"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U5",
        "name": "Stream Parsing and Aggregation",
        "components": [
          "stream_parsing",
          "measurement_aggregation"
        ],
        "unit_type": "runtime",
        "rationale": "Stream Parsing cleans the received bytes and splits them into temperature, humidity and soil moisture values, and Measurement Aggregation keeps a sliding window of the last 10 readings of each measurement and computes their means. Parsing feeds aggregation on every received line, so they form one coherent processing function and are grouped to avoid a communication hop per line. Neither requires local hardware or the operator interface, so they are kept separate from the connectivity and interface stages.",
        "grouping_criteria": [
          "cohesion",
          "coupling",
          "device_binding"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [
          "stream_parsing -> measurement_aggregation"
        ],
        "external_dependencies": [
          "app_bluetooth_connection -> stream_parsing",
          "measurement_aggregation -> dashboard_display",
          "measurement_aggregation -> trend_chart"
        ],
        "execution_constraint": "flexible",
        "characteristics": [
          "stateful"
        ],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U6",
        "name": "Farmer Interface",
        "components": [
          "dashboard_display",
          "trend_chart",
          "command_input"
        ],
        "unit_type": "runtime",
        "rationale": "These components form the farmer-facing interface of the Android app: tiles with mean temperature, humidity and soil moisture (plus a rainfall placeholder), a line chart of temperature readings in the current window, and a text field for typing commands to the sensor node. They require direct access to the local operator interface, so they are grouped together and kept separate from components with different execution characteristics.",
        "grouping_criteria": [
          "device_binding",
          "cohesion"
        ],
        "cohesion": "medium",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [],
        "external_dependencies": [
          "measurement_aggregation -> dashboard_display",
          "measurement_aggregation -> trend_chart",
          "command_input -> app_bluetooth_connection"
        ],
        "execution_constraint": "device_bound",
        "characteristics": [
          "user_interaction",
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
        "U6"
      ],
      "edges": [
        {
          "source": "U1",
          "target": "U2",
          "component_edges": [
            "temperature_humidity_sensing -> measurement_packaging",
            "soil_moisture_sensing -> measurement_packaging",
            "temperature_humidity_sensing -> sensor_command_handler",
            "soil_moisture_sensing -> sensor_command_handler"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "periodic",
            "volume": "low",
            "latency_sensitivity": "unknown"
          }
        },
        {
          "source": "U2",
          "target": "U3",
          "component_edges": [
            "measurement_packaging -> sensor_bluetooth_link",
            "sensor_command_handler -> sensor_bluetooth_link"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "periodic",
            "volume": "low",
            "latency_sensitivity": "unknown"
          }
        },
        {
          "source": "U3",
          "target": "U2",
          "component_edges": [
            "sensor_bluetooth_link -> sensor_command_handler"
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
          "source": "U3",
          "target": "U4",
          "component_edges": [
            "sensor_bluetooth_link -> app_bluetooth_connection"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "periodic",
            "volume": "low",
            "latency_sensitivity": "unknown"
          }
        },
        {
          "source": "U4",
          "target": "U3",
          "component_edges": [
            "app_bluetooth_connection -> sensor_bluetooth_link"
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
          "source": "U4",
          "target": "U5",
          "component_edges": [
            "app_bluetooth_connection -> stream_parsing"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "periodic",
            "volume": "low",
            "latency_sensitivity": "unknown"
          }
        },
        {
          "source": "U5",
          "target": "U6",
          "component_edges": [
            "measurement_aggregation -> dashboard_display",
            "measurement_aggregation -> trend_chart"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "periodic",
            "volume": "low",
            "latency_sensitivity": "unknown"
          }
        },
        {
          "source": "U6",
          "target": "U4",
          "component_edges": [
            "command_input -> app_bluetooth_connection"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "event_driven",
            "volume": "low",
            "latency_sensitivity": "unknown"
          }
        }
      ]
    },
    "granularity_summary": {
      "number_of_components": 12,
      "number_of_execution_units": 6,
      "total_edges": 15,
      "internal_edges": 2,
      "cut_edges": 13,
      "overall_strategy": "Task-level granularity: components requiring local sensor, Bluetooth or operator-interface access are grouped by shared function (sensing, sensor Bluetooth link, app Bluetooth connectivity, farmer interface), and each group is kept separate from the components without such requirements. Sensor-side formatting and command handling form one unit, and stream parsing with sliding-window aggregation forms another cohesive stateful unit."
    }
  }
}
```
