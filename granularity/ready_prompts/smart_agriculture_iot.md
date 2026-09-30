<!-- AUTO-GENERATED from prompt.md + input/smart_agriculture_iot.json. Copy ALL of this file into the LLM chat. Save the reply as output/smart_agriculture_iot.json. Do not edit: ask Claude to regenerate it. -->

You are an expert in IoT systems, Edge/Cloud computing, distributed systems and application deployment. You act as the **Granularity Analysis** stage of a pre-deployment offloading pipeline:

```
functional graph -> [GRANULARITY ANALYSIS] -> resource estimation -> offloadability analysis -> deployment planner
```

## Your task

The functional graph of an IoT application is given below. It is already correct.

- Do NOT analyse source code.
- Do NOT reconstruct, rename, split or invent components.
- Use ONLY the facts stated in the graph. Do not invent implementation details, models, libraries, hardware, dependencies or execution characteristics that the graph does not state. You may mention a model or library name only if it appears in the graph; otherwise describe the component by its function (e.g. "object detection", not a specific model).
- Your ONLY job is to group the existing components into **execution units**: the deployable entities that the next stages will size, classify as offloadable or non-offloadable, and place on IoT, Edge or Cloud nodes.

## Scope of this stage

Each stage of the pipeline answers one question. Answer ONLY yours:

| Stage | Question |
|---|---|
| **Granularity (you)** | What should be grouped together, and which characteristics of each unit matter for deployment? |
| Resource Estimation | How much CPU, GPU, memory, storage and network does each unit need? |
| Offloadability | Can each unit run remotely, and under which constraints? |
| Deployment Planner | Where does each unit actually run? |

Therefore:

- Do NOT recommend a placement. Never write "Edge placement is preferred", "should run in the Cloud", "keep on the device" or name any target node or tier.
- Do NOT estimate resources. Never give resource levels or values such as "CPU = high", "2 GB RAM" or "low CPU load".
- Instead, describe the **characteristics** of each unit that the next stages will need, using the tags listed below. For example: "High frame-rate input and latency-sensitive output should be considered when determining the placement of this unit."

You do this in two steps:

1. **Select the offloading granularity level** of the application.
2. **Form the execution units** according to that level.

## Step 1: Granularity levels

Choose exactly ONE level for the application:

| Level | Execution unit | Communication overhead | Placement flexibility |
|---|---|---|---|
| `application` | The whole application forms one unit. Only components requiring direct access to local hardware or the local operator interface stay apart. | Lowest | Lowest |
| `task` | Each unit is a group of cohesive components forming one functional stage or service (e.g. acquisition, preprocessing, analysis, storage). | Medium | Medium |
| `method` | Each unit is a single node of the graph (one function or method), so every node can be placed independently. | Highest | Highest |

Choose the level with these guidelines:

- **`application`**: few components, strong coupling across the whole graph, intensive data exchange between almost all components, and little benefit from splitting the application across several nodes.
- **`task`**: the graph contains identifiable functional stages with strong coupling inside each stage and weaker coupling between stages, or the stages have heterogeneous resource needs or execution constraints. This is the usual level for IoT/Edge applications.
- **`method`**: the nodes are fine-grained functions, several of them perform independent processing and are loosely coupled (little data exchanged), and independent placement brings a clear benefit that outweighs the communication overhead.

The nodes of the input graph are the finest level available: a unit may contain one or more nodes, but a node is never split.

## Step 2: Grouping criteria (apply all of them)

1. **Functional cohesion**: components that together realise one coherent function belong in the same unit.
2. **Coupling / communication**: components linked by frequent or high-volume data flows should be grouped to avoid network overhead.
3. **Avoid over-fragmentation**: do not create one unit per component unless each component really needs independent deployment.
4. **Avoid over-grouping**: do not merge weakly related components.
5. **Hardware binding**: components that require direct access to local hardware (sensors, actuators, camera, speaker) or to the local operator interface are grouped only with components that share this requirement, and are kept separate from components with different execution characteristics (e.g. model inference, storage, analytics). Otherwise the hardware requirement would extend to the whole unit.
6. **Scalability**: components with very different scaling needs (e.g. a stateless compute stage vs. a persistent store) stay separate so they can be replicated independently.
7. **Latency**: components on a latency-critical path stay together when splitting them would add network hops.

## Characteristic tags

Use only these tags in `characteristics` (as many as apply):

| Tag | Meaning |
|---|---|
| `hardware_access` | accesses a sensor, actuator, camera, speaker or other local hardware |
| `user_interaction` | provides a user interface or interacts with an operator |
| `ml_inference` | runs a machine learning / deep learning model |
| `high_frequency_input` | receives data at a high rate (e.g. video frames, sensor streams) |
| `latency_sensitive` | its output is needed in (near) real time |
| `stateful` | keeps state across executions (tracking, buffers, sessions) |
| `stateless` | no state kept between executions |
| `persistent_storage` | stores data durably (database, files, logs) |
| `external_service_dependency` | depends on a remote service or repository (model hub, API) |
| `event_driven` | runs only when a specific event occurs |

## Output format

Reply with ONE JSON object only, inside a single ```json code block, with no text before or after it. Do not create a file, canvas or artifact: reply directly in the chat.

```json
{
  "application_id": "<copy from input>",
  "granularity": {
    "level": "application | task | method",
    "justification": "<why this level fits this application>",
    "alternatives": [
      {
        "level": "<one of the two levels not selected>",
        "rejected_because": "<why it fits less well>"
      }
    ]
  },
  "execution_units": [
    {
      "unit_id": "U1",
      "name": "<short descriptive name>",
      "components": ["<component id>"],
      "unit_type": "runtime | initialization",
      "rationale": "<why these components are grouped, or kept alone>",
      "grouping_criteria": ["cohesion | coupling | device_binding | latency | scalability | independence"],
      "cohesion": "low | medium | high",
      "communication_intensity_with_other_units": "low | medium | high",
      "internal_dependencies": ["<source_id> -> <target_id>"],
      "external_dependencies": ["<source_id> -> <target_id>"],
      "execution_constraint": "device_bound | flexible | unknown",
      "characteristics": ["<tags from the table above>"],
      "deployment_role": "service | dependency",
      "supports": ["<unit ids this unit prepares, only for deployment_role = dependency>"]
    }
  ],
  "unit_graph": {
    "nodes": ["U1", "U2"],
    "edges": [
      {
        "source": "U1",
        "target": "U2",
        "component_edges": ["<source_id> -> <target_id>"],
        "types": ["<edge type from input>"],
        "data_characteristics": {
          "frequency": "continuous | periodic | event_driven | startup_only | unknown",
          "volume": "low | medium | high | unknown",
          "latency_sensitivity": "low | medium | high | unknown"
        }
      }
    ]
  },
  "granularity_summary": {
    "number_of_components": 0,
    "number_of_execution_units": 0,
    "total_edges": 0,
    "internal_edges": 0,
    "cut_edges": 0,
    "overall_strategy": "<one or two sentences>"
  }
}
```

## Rules for the output

- `granularity.level` is exactly one of `application`, `task`, `method`, and `alternatives` covers the two other levels.
- The units must match the selected level:
  - `application`: one unit with all components, except the components requiring direct access to local hardware or to the local operator interface, which form a separate unit if there are any.
  - `task`: one unit per functional stage.
  - `method`: one unit per node.
- `unit_id` values are U1, U2, U3, ... in order.
- `components` contains ONLY ids that exist in the input `nodes`.
- Every component id appears in **exactly one** unit.
- `internal_dependencies`: input edges whose source and target are both in this unit.
- `external_dependencies`: input edges with exactly one end in this unit.
- `unit_graph.edges`: one entry per ordered pair of units connected by at least one input edge.
- `data_characteristics` describes the flow across the boundary qualitatively, from what the graph states (e.g. frames sent on every processed frame = `continuous`; an alert sent only when a crime is detected = `event_driven`; models loaded at startup = `startup_only`). It is NOT a bandwidth or latency estimate. Use `unknown` when the graph gives no basis.
- `cut_edges` = number of input edges between different units; `internal_edges` = `total_edges` - `cut_edges`.
- `execution_constraint`: `device_bound` only if the unit contains a component with `hardware_access` or local `user_interaction` on the device; otherwise `flexible` (or `unknown` if the graph does not say). It states a constraint, not a placement: the Offloadability stage confirms it.
- `characteristics` uses ONLY tags from the table.
- `unit_type`:
  - `runtime`: the unit takes part in the normal processing of the application, on every input or event.
  - `initialization`: the unit only runs at startup or setup time (e.g. loading or downloading models, configuration). The Deployment Planner does not treat it as an independently scalable runtime service.
- `deployment_role`:
  - `service`: a runtime unit that is deployed and possibly replicated on its own. All `runtime` units are `service`.
  - `dependency`: an `initialization` unit that prepares other units (e.g. provides their models). It is deployed together with the units listed in `supports`, not as a separate service.
- `supports`: for a `dependency`, the ids of the units it prepares (the targets of its outgoing edges). For a `service`, an empty list.
- `rationale` and `overall_strategy` explain the grouping only (cohesion, coupling, dependencies, shared or separate characteristics).

## Forbidden content (all fields)

The following belong to later stages and must NOT appear anywhere in your answer:

- **Tier or node names used as a destination**: "Edge", "Cloud", "fog", "server", "GPU node", "near the device", "on the device", "remote".
- **Placement verbs**: "place", "placement", "deploy on", "run on", "host on", "should be offloaded", "offloadable to".
- **Offloadability classification**: "offloadable", "non-offloadable", "can be offloaded", "cannot run remotely", "inherits its hardware constraint". Whether a unit can execute remotely is decided by the Offloadability stage.
- **Resource amounts or intensity levels**: "high CPU", "low CPU load", "highly compute-intensive", "GPU-intensive", "needs a GPU", "benefits strongly from a GPU", "large memory", "data-heavy", or any number of cores, GB or Mbps.

Express these aspects only through `execution_constraint` and the `characteristics` tags.

Example:

- Wrong: "U5 is highly compute-intensive and should be offloaded to an Edge GPU node."
- Right: "object_detection feeds object_tracking on every processed frame, so they are grouped to avoid a network hop per frame." with characteristics `["ml_inference", "high_frequency_input", "stateful", "latency_sensitive"]`.
- Wrong: "U1 is kept apart from every offloadable component, so no offloadable processing inherits its hardware constraint."
- Right: "These components require direct access to the local operator interface and audio hardware, so they are grouped together and kept separate from components with different execution characteristics."
- No field may contain a placement recommendation or a resource estimate.

Before answering, check that the units match the selected level, that none of the forbidden content appears anywhere, that each unit has a `unit_type` and a consistent `deployment_role`, that no fact outside the graph was added, that every component is assigned exactly once and that the counts in `granularity_summary` match the input.

## Input functional graph

```json
{
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
    { "source": "temperature_humidity_sensing", "target": "measurement_packaging", "type": "data_flow" },
    { "source": "soil_moisture_sensing", "target": "measurement_packaging", "type": "data_flow" },
    { "source": "temperature_humidity_sensing", "target": "sensor_command_handler", "type": "data_flow" },
    { "source": "soil_moisture_sensing", "target": "sensor_command_handler", "type": "data_flow" },
    { "source": "measurement_packaging", "target": "sensor_bluetooth_link", "type": "data_flow" },
    { "source": "sensor_command_handler", "target": "sensor_bluetooth_link", "type": "data_flow" },
    { "source": "sensor_bluetooth_link", "target": "sensor_command_handler", "type": "control_flow" },
    { "source": "sensor_bluetooth_link", "target": "app_bluetooth_connection", "type": "data_flow" },
    { "source": "app_bluetooth_connection", "target": "sensor_bluetooth_link", "type": "control_flow" },
    { "source": "device_discovery", "target": "app_bluetooth_connection", "type": "control_flow" },
    { "source": "command_input", "target": "app_bluetooth_connection", "type": "data_flow" },
    { "source": "app_bluetooth_connection", "target": "stream_parsing", "type": "data_flow" },
    { "source": "stream_parsing", "target": "measurement_aggregation", "type": "data_flow" },
    { "source": "measurement_aggregation", "target": "dashboard_display", "type": "data_flow" },
    { "source": "measurement_aggregation", "target": "trend_chart", "type": "data_flow" }
  ]
}
```
