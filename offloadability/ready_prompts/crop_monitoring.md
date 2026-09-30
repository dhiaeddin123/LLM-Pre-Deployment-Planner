<!-- AUTO-GENERATED from prompt.md + input/crop_monitoring.json. Copy ALL of this file into the LLM chat. Save the reply as output/crop_monitoring.json. Do not edit. -->

You are an expert in IoT systems, computation offloading, Edge/Cloud computing and distributed systems. You act as the **Offloadability Analysis** stage of a pre-deployment offloading pipeline:

```
functional graph -> granularity analysis -> resource estimation -> [OFFLOADABILITY ANALYSIS] -> deployment planner
```

## Your task

You receive:

1. The **functional graph** (components and their functions).
2. The **granularity result**: execution units, characteristics, unit graph.
3. The **resource estimation result**: per-unit resource profiles (with constraints, platform, provenance) and per-edge communication requirements (bandwidth, mechanism, boundary, latency sensitivity).

All three are given and correct. For EVERY execution unit, decide whether it can execute on a **remote host** (any machine other than the device where it currently runs), and under which conditions.

## Scope of this stage

| Stage | Question |
|---|---|
| Granularity | What should be grouped together? (done) |
| Resource Estimation | How much does each unit need? (done) |
| **Offloadability (you)** | Can each unit run remotely, and under which constraints? |
| Deployment Planner | Where does each unit run, with how many replicas? |

Therefore:

- You decide **feasibility and constraints**, not placement. Never choose between Edge and Cloud, never name a node, never recommend replicas.
- You may say "remote host" and state what that remote host or its link must provide (GPU, bandwidth, proximity, storage, access to an external service).
- Do NOT change units, resource values or edges. Use them as given.
- Use ONLY facts in the input. Every blocking factor and condition carries a `provenance` (`observed`, `inferred`, `assumed`, `unknown`), as in the resource stage.

## Step 1: Identify anchors

An **anchor** is a physical device the application cannot leave because some component needs something that only exists there: a sensor or actuator, a camera, a speaker, a local operator interface, a platform API tied to the device (e.g. the Android Bluetooth API on the user's phone).

List each anchor once, with the evidence. Units that must stay on an anchor are **anchored** to it.

## Step 2: Classify every unit

Use exactly one status:

| Status | Meaning |
|---|---|
| `non_offloadable` | The unit needs something that exists only on its anchor. At least one blocking factor of type `hardware_binding`, `local_user_interaction` or `device_platform_api` with provenance `observed` or `inferred`. |
| `conditionally_offloadable` | The unit can run remotely, but only if specific conditions are met (e.g. a GPU, a minimum bandwidth or proximity to an anchor, a relay path, or the verification of an `assumed` fact). |
| `offloadable` | The unit can run remotely with no condition beyond ordinary compute and network availability. |
| `follows_supported_units` | Only for `initialization` units with `deployment_role` = `dependency`: they run wherever the units they support run. |

Rules:

- The granularity `execution_constraint` is a hint, not the answer. Verify it against the component functions. Report whether you agree in `agrees_with_granularity` and explain any disagreement.
- A blocking factor based only on an `assumed` fact does NOT make a unit `non_offloadable`. The unit becomes `conditionally_offloadable`, with a condition of type `verify_assumption`.
- A unit that currently runs on an anchor but needs nothing specific to it (pure computation, parsing, aggregation, formatting, storage) is NOT anchored merely because of where it runs today.
- `ml_inference` or `gpu.requirement` = `required` is not a reason to be `non_offloadable`. It is usually a condition on the remote host (`gpu_required`).

## Step 3: Conditions for remote execution

For every `conditionally_offloadable` (and, where relevant, `offloadable`) unit, list the conditions a remote host or its link must satisfy. Use these condition types:

| Type | Meaning | Derived from |
|---|---|---|
| `gpu_required` | the remote host must provide a GPU with at least the given memory | resource `gpu` |
| `min_bandwidth_mbps` | the link between the remote host and a given unit must carry at least this bandwidth | edges that become network links if the unit is offloaded |
| `network_proximity` | the remote host must be close to a given anchored unit: `same_site` (one hop / local network), `regional`, `any` | latency sensitivity of those edges: `high` -> `same_site`, `medium` -> `regional`, `low` -> `any`, `unknown` -> no condition, but mention it |
| `relay_required` | the anchored peer has no direct IP connectivity; traffic must pass through another device (e.g. a Bluetooth-only sensor node reachable only via the phone) | `current_mechanism` / `boundary` of the anchor's edges |
| `external_service_access` | the remote host must reach an external service (e.g. a model hub) | `external_service_dependency` |
| `persistent_storage` | the remote host must provide durable storage of the given size | resource `storage` |
| `state_handling` | the unit keeps state: offloading requires a single active instance, sticky routing or state transfer | `stateful` characteristic |
| `verify_assumption` | the decision depends on an assumed fact that must be confirmed | provenance `assumed` |

## Step 4: Communication impact of offloading

For each unit, list its communication with every neighbouring unit (from `communication_requirements`) and state which flows would cross a network if this unit were offloaded **while its anchored neighbours stay on their anchors**:

- A `logical` edge to an anchored unit becomes network traffic.
- A `physical` edge stays a device link, but may require a relay.
- A `hardware` edge cannot be separated: if a unit has a `hardware` edge to an anchored unit, it is itself anchored.
- Edges to other non-anchored units are left to the Deployment Planner: report them, but do not count them as added traffic.

`added_network_traffic_mbps` = exact sum of `bandwidth_mbps` of the edges between this unit and ANCHORED units that would become network traffic (no rounding).

## Output format

Reply with ONE JSON object only, inside a single ```json code block, with no text before or after it. Do not create a file, canvas or artifact.

```json
{
  "application_id": "<copy from input>",
  "anchors": [
    {
      "anchor_id": "A1",
      "description": "<the physical device, e.g. 'Arduino Uno sensor node with DHT22, soil moisture sensor and HC-05 module'>",
      "anchored_units": ["<unit ids>"],
      "evidence": ["<facts from the input>"],
      "network_connectivity": "<how this device communicates with other devices, from the input: e.g. 'Bluetooth serial only', 'IP network', 'unknown'>",
      "provenance": "observed | inferred | assumed | unknown"
    }
  ],
  "offloadability_profiles": [
    {
      "unit_id": "U1",
      "name": "<copy>",
      "unit_type": "<copy>",
      "current_platform": "<copy from resource profile>",
      "status": "non_offloadable | conditionally_offloadable | offloadable | follows_supported_units",
      "anchored_to": "<anchor id, or null>",
      "follows_units": ["<only for follows_supported_units: the supported unit ids>"],
      "agrees_with_granularity": true,
      "disagreement_reason": null,
      "blocking_factors": [
        {
          "type": "hardware_binding | local_user_interaction | device_platform_api | data_locality",
          "component": "<component id>",
          "evidence": "<fact from the input>",
          "provenance": "observed | inferred | assumed | unknown"
        }
      ],
      "conditions": [
        {
          "type": "gpu_required | min_bandwidth_mbps | network_proximity | relay_required | external_service_access | persistent_storage | state_handling | verify_assumption",
          "requirement": "<human-readable requirement>",
          "value": null,
          "unit": "<GB | Mbps | same_site | regional | any | null>",
          "related_unit": "<peer unit id, if the condition concerns a link, else null>",
          "basis": "<which input field it comes from>",
          "provenance": "observed | inferred | assumed | unknown"
        }
      ],
      "communication_if_offloaded": [
        {
          "peer_unit": "<unit id>",
          "direction": "incoming | outgoing",
          "peer_is_anchored": true,
          "current_boundary": "logical | physical | hardware | unknown",
          "bandwidth_mbps": 0.0,
          "latency_sensitivity": "<copy level>",
          "becomes_network_traffic": true
        }
      ],
      "added_network_traffic_mbps": 0.0,
      "confidence": "low | medium | high",
      "rationale": "<why this status, citing the evidence>"
    }
  ],
  "summary": {
    "offloadable": ["<unit ids>"],
    "conditionally_offloadable": ["<unit ids>"],
    "non_offloadable": ["<unit ids>"],
    "follows_supported_units": ["<unit ids>"],
    "local_core": {
      "<anchor id>": ["<units that must stay on this anchor>"]
    },
    "disagreements_with_granularity": ["<unit ids>"],
    "observations": ["<short factual observations>"]
  }
}
```

## Rules for the output

- One entry in `offloadability_profiles` per execution unit, same `unit_id`s, same order.
- `non_offloadable` units have `anchored_to` set and at least one blocking factor with provenance `observed` or `inferred`. All other statuses have `anchored_to` = null.
- `conditionally_offloadable` units have at least one condition. `offloadable` units may list informative conditions such as `state_handling`, but none of type `gpu_required`, `network_proximity` = `same_site`, `relay_required` or `verify_assumption`.
- `follows_supported_units` only for initialization dependency units, with `follows_units` = their `supports` list.
- Numbers for `gpu_required`, `min_bandwidth_mbps` and `persistent_storage` are copied from the resource estimation, not re-estimated.
- `communication_if_offloaded` lists every edge that touches the unit. `added_network_traffic_mbps` sums, without rounding, the `bandwidth_mbps` of the entries with `peer_is_anchored` = true and `becomes_network_traffic` = true.
- The summary lists every unit exactly once across the four status lists.
- No Edge/Cloud choice, no node, no replica count anywhere.

Before answering, check that every unit has exactly one status consistent with the rules, that every blocking factor and condition has a provenance, that no `assumed` fact alone makes a unit non-offloadable, that condition values match the resource estimation, that the added-traffic sums are exact, and that no placement decision appears.

## Input

```json
{
  "application_id": "crop_monitoring",
  "functional_graph": {
    "application_id": "crop_monitoring",
    "nodes": [
      {
        "id": "sensor_acquisition",
        "name": "Sensor Acquisition",
        "function": "Collects soil moisture and temperature data"
      },
      {
        "id": "data_preprocessing",
        "name": "Data Preprocessing",
        "function": "Filters and normalizes sensor measurements"
      },
      {
        "id": "crop_analysis",
        "name": "Crop Analysis",
        "function": "Analyzes measurements to determine crop conditions"
      },
      {
        "id": "decision_engine",
        "name": "Decision Engine",
        "function": "Generates irrigation decisions"
      },
      {
        "id": "cloud_storage",
        "name": "Cloud Storage",
        "function": "Stores historical agricultural data"
      }
    ],
    "edges": [
      {
        "source": "sensor_acquisition",
        "target": "data_preprocessing",
        "type": "data_flow"
      },
      {
        "source": "data_preprocessing",
        "target": "crop_analysis",
        "type": "data_flow"
      },
      {
        "source": "crop_analysis",
        "target": "decision_engine",
        "type": "data_flow"
      },
      {
        "source": "crop_analysis",
        "target": "cloud_storage",
        "type": "data_flow"
      }
    ]
  },
  "granularity": {
    "application_id": "crop_monitoring",
    "granularity": {
      "level": "task",
      "justification": "The graph is a short pipeline with identifiable functional stages: sensor acquisition of soil moisture and temperature, measurement processing (filtering, normalization and crop-condition analysis), irrigation decision generation, and storage of historical agricultural data. The stages have heterogeneous execution characteristics. Acquisition requires direct access to sensor hardware, storage keeps data durably, and processing and decision generation have neither requirement. Coupling is strongest between data_preprocessing and crop_analysis, because preprocessed measurements are consumed only by the analysis. The analysis results then fan out to two consumers with different functions. Task-level units group the tightly coupled processing steps and keep stages with different characteristics separate.",
      "alternatives": [
        {
          "level": "application",
          "rejected_because": "Grouping all components without a hardware requirement into one unit would merge measurement processing, irrigation decision generation and durable storage of historical data. These serve different functions, and the storage stage has different scaling needs from the processing stages. The graph does not indicate intensive data exchange between all components: analysis results simply fan out to decision generation and storage. A single unit would therefore join weakly related components without a clear communication benefit."
        },
        {
          "level": "method",
          "rejected_because": "One unit per node would separate data_preprocessing from crop_analysis, although preprocessing exists only to feed the analysis and no other component consumes its output. Splitting this pair would add a communication hop on the main processing path without any benefit from independent handling. The remaining nodes are already separated at task level."
        }
      ]
    },
    "execution_units": [
      {
        "unit_id": "U1",
        "name": "Sensor Acquisition",
        "components": [
          "sensor_acquisition"
        ],
        "unit_type": "runtime",
        "rationale": "Sensor Acquisition collects soil moisture and temperature data, which requires direct access to the sensors. No other component shares this requirement, so it forms its own unit and is kept separate from components with different execution characteristics.",
        "grouping_criteria": [
          "device_binding",
          "independence"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [],
        "external_dependencies": [
          "sensor_acquisition -> data_preprocessing"
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
        "name": "Measurement Processing and Crop Analysis",
        "components": [
          "data_preprocessing",
          "crop_analysis"
        ],
        "unit_type": "runtime",
        "rationale": "Data Preprocessing filters and normalizes the sensor measurements, and Crop Analysis analyzes them to determine crop conditions. The preprocessed measurements are consumed only by the analysis, so both form one coherent processing function and are grouped to avoid a communication hop between them. Neither requires sensor hardware or durable storage, so they are kept separate from the acquisition and storage stages.",
        "grouping_criteria": [
          "cohesion",
          "coupling",
          "device_binding"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [
          "data_preprocessing -> crop_analysis"
        ],
        "external_dependencies": [
          "sensor_acquisition -> data_preprocessing",
          "crop_analysis -> decision_engine",
          "crop_analysis -> cloud_storage"
        ],
        "execution_constraint": "flexible",
        "characteristics": [],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U3",
        "name": "Irrigation Decision",
        "components": [
          "decision_engine"
        ],
        "unit_type": "runtime",
        "rationale": "The Decision Engine generates irrigation decisions from the crop-condition analysis. This decision function is distinct from measurement processing and from historical data storage, and it consumes only the analysis results. It is therefore kept as its own stage so its characteristics can be assessed independently.",
        "grouping_criteria": [
          "cohesion",
          "independence"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [],
        "external_dependencies": [
          "crop_analysis -> decision_engine"
        ],
        "execution_constraint": "flexible",
        "characteristics": [],
        "deployment_role": "service",
        "supports": []
      },
      {
        "unit_id": "U4",
        "name": "Historical Data Storage",
        "components": [
          "cloud_storage"
        ],
        "unit_type": "runtime",
        "rationale": "The cloud_storage component stores historical agricultural data. It is a durable storage stage whose scaling needs differ from the processing and decision stages, so it is kept separate.",
        "grouping_criteria": [
          "scalability",
          "independence"
        ],
        "cohesion": "high",
        "communication_intensity_with_other_units": "low",
        "internal_dependencies": [],
        "external_dependencies": [
          "crop_analysis -> cloud_storage"
        ],
        "execution_constraint": "flexible",
        "characteristics": [
          "persistent_storage"
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
        "U4"
      ],
      "edges": [
        {
          "source": "U1",
          "target": "U2",
          "component_edges": [
            "sensor_acquisition -> data_preprocessing"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "unknown",
            "volume": "unknown",
            "latency_sensitivity": "unknown"
          }
        },
        {
          "source": "U2",
          "target": "U3",
          "component_edges": [
            "crop_analysis -> decision_engine"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "unknown",
            "volume": "unknown",
            "latency_sensitivity": "unknown"
          }
        },
        {
          "source": "U2",
          "target": "U4",
          "component_edges": [
            "crop_analysis -> cloud_storage"
          ],
          "types": [
            "data_flow"
          ],
          "data_characteristics": {
            "frequency": "unknown",
            "volume": "unknown",
            "latency_sensitivity": "unknown"
          }
        }
      ]
    },
    "granularity_summary": {
      "number_of_components": 5,
      "number_of_execution_units": 4,
      "total_edges": 4,
      "internal_edges": 1,
      "cut_edges": 3,
      "overall_strategy": "Task-level granularity: sensor acquisition, which requires sensor hardware, forms its own unit, and the tightly coupled preprocessing and crop analysis form one processing unit. Irrigation decision generation and historical data storage remain separate stages because their functions and characteristics differ."
    }
  },
  "resource_estimation": {
    "application_id": "crop_monitoring",
    "estimation_method": "heuristic_llm",
    "assumptions": [
      "There is one sensor source producing one soil-moisture and one temperature reading per sample.",
      "One sample is taken every 10 s (0.1 samples/s).",
      "One soil-moisture and temperature sample with timestamp is about 0.05 kB.",
      "One crop-condition result and one stored history record are each about 0.1 kB.",
      "Crop analysis is rule-based or statistical; the input names no ML model.",
      "Decision generation is rule-based logic evaluated on one crop-condition result per sample.",
      "Historical data is retained for one year, with a storage overhead factor of about 2.",
      "The platform of every unit is unknown; no platform baseline can be derived."
    ],
    "platform_baselines": [
      {
        "platform": "unknown",
        "units": [
          "U1",
          "U2",
          "U3",
          "U4"
        ],
        "cpu_cores": null,
        "memory_gb": null,
        "basis": "The input does not state the runtime or platform of any unit, or whether units share one. No baseline can be derived.",
        "confidence": "low"
      }
    ],
    "resource_profiles": [
      {
        "unit_id": "U1",
        "name": "Sensor Acquisition",
        "unit_type": "runtime",
        "platform": "unknown",
        "workload_pattern": "periodic",
        "constraints": {
          "execution_constraint": "device_bound",
          "deployment_role": "service",
          "binding_characteristics": [
            "hardware_access"
          ],
          "required_hardware_or_platform": [
            "Soil moisture sensor (type not stated)",
            "Temperature sensor (type not stated)"
          ]
        },
        "evidence": {
          "observed_facts": [
            "Collects soil moisture and temperature data."
          ],
          "inferred_characteristics": [
            "It reads two scalar measurements per sample.",
            "It produces a small data stream for preprocessing."
          ]
        },
        "cpu": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "typical_cores": null,
          "peak_cores": null,
          "native_estimate": null,
          "not_comparable_reason": "The platform executing sensor acquisition is not stated and may be a microcontroller, so an x86-64 core figure has no basis.",
          "basis": "Reading two scalar sensor values per sample is a trivial computation at any plausible sampling rate."
        },
        "memory": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "typical_gb": null,
          "peak_gb": null,
          "native_estimate": null,
          "not_comparable_reason": "The platform is not stated and may be a microcontroller, so a GB figure has no basis.",
          "basis": "Only the latest two readings need to be held."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "inferred",
          "assumption_refs": [],
          "memory_gb": 0,
          "basis": "Collecting sensor data involves no model or parallel computation."
        },
        "storage": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "size_gb": 0,
          "persistent": false,
          "growth": "none",
          "basis": "The input describes no storage for acquisition. History is kept in U4."
        },
        "network": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "One soil-moisture and temperature sample with timestamp is about 0.05 kB."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 0,
          "potential_egress_mbps": 4e-06,
          "basis": "Potential egress is U1 -> U2 (0.000004 Mbps, boundary unknown). The unit has no incoming unit-graph edge and no known physical edge."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "medium",
        "assumptions": [],
        "how_to_measure": "Log the timestamp and size of every sample emitted by the acquisition code to obtain the real sampling rate and payload size, and profile the acquisition process with the platform's own tools once the platform is known."
      },
      {
        "unit_id": "U2",
        "name": "Measurement Processing and Crop Analysis",
        "unit_type": "runtime",
        "platform": "unknown",
        "workload_pattern": "periodic",
        "constraints": {
          "execution_constraint": "flexible",
          "deployment_role": "service",
          "binding_characteristics": [],
          "required_hardware_or_platform": []
        },
        "evidence": {
          "observed_facts": [
            "Data Preprocessing filters and normalizes sensor measurements.",
            "Crop Analysis analyzes measurements to determine crop conditions."
          ],
          "inferred_characteristics": [
            "It processes two scalar values per sample.",
            "Filtering implies a small window of recent measurements kept across samples.",
            "It produces one crop-condition result per sample for decision generation and storage."
          ]
        },
        "cpu": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "Crop analysis is rule-based or statistical; the input names no ML model."
          ],
          "typical_cores": 0.01,
          "peak_cores": 0.05,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Filtering, normalization and rule-based or statistical analysis of two values every 10 s. The peak covers a more elaborate analysis step. If the real analysis uses a model or a much higher rate, this estimate must be revised."
        },
        "memory": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "Crop analysis is rule-based or statistical; the input names no ML model."
          ],
          "typical_gb": 0.01,
          "peak_gb": 0.01,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "A small filter window of recent measurements and analysis parameters."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "assumed",
          "assumption_refs": [
            "Crop analysis is rule-based or statistical; the input names no ML model."
          ],
          "memory_gb": 0,
          "basis": "No model is named. The input does not rule one out, so the absence of a GPU need rests on the assumed analysis method."
        },
        "storage": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "size_gb": 0,
          "persistent": false,
          "growth": "none",
          "basis": "The input describes no storage in this unit. Historical data is stored by U4."
        },
        "network": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "One soil-moisture and temperature sample with timestamp is about 0.05 kB.",
            "One crop-condition result and one stored history record are each about 0.1 kB."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 4e-06,
          "potential_egress_mbps": 1.6e-05,
          "basis": "Potential ingress is U1 -> U2 (0.000004). Potential egress is U2 -> U3 (0.000008) + U2 -> U4 (0.000008). All boundaries are unknown."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [],
        "how_to_measure": "Time the preprocessing and analysis functions per sample with a profiler, measure resident memory of the process, and confirm whether the analysis uses a model."
      },
      {
        "unit_id": "U3",
        "name": "Irrigation Decision",
        "unit_type": "runtime",
        "platform": "unknown",
        "workload_pattern": "periodic",
        "constraints": {
          "execution_constraint": "flexible",
          "deployment_role": "service",
          "binding_characteristics": [],
          "required_hardware_or_platform": []
        },
        "evidence": {
          "observed_facts": [
            "Decision Engine generates irrigation decisions."
          ],
          "inferred_characteristics": [
            "It evaluates crop-condition results to produce irrigation decisions.",
            "The input does not state where the decisions go."
          ]
        },
        "cpu": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "Decision generation is rule-based logic evaluated on one crop-condition result per sample."
          ],
          "typical_cores": 0.01,
          "peak_cores": 0.01,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Evaluating decision logic on one small result every 10 s. The actual demand is below the smallest grid value."
        },
        "memory": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "Decision generation is rule-based logic evaluated on one crop-condition result per sample."
          ],
          "typical_gb": 0.001,
          "peak_gb": 0.001,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Decision rules and the latest crop-condition result. The actual demand is below the smallest grid value."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "assumed",
          "assumption_refs": [
            "Decision generation is rule-based logic evaluated on one crop-condition result per sample."
          ],
          "memory_gb": 0,
          "basis": "No model is named for decision generation. The absence of a GPU need rests on the assumed rule-based logic."
        },
        "storage": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "size_gb": 0,
          "persistent": false,
          "growth": "none",
          "basis": "The input describes no storage in this unit."
        },
        "network": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "One crop-condition result and one stored history record are each about 0.1 kB."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 8e-06,
          "potential_egress_mbps": 0,
          "basis": "Potential ingress is U2 -> U3 (0.000008, boundary unknown). The unit graph has no outgoing edge from this unit, so any output of the decisions (e.g. to an irrigation system) is not modelled."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [],
        "how_to_measure": "Log decision evaluations with timestamps to obtain their real rate, and time the decision function per call with a profiler."
      },
      {
        "unit_id": "U4",
        "name": "Historical Data Storage",
        "unit_type": "runtime",
        "platform": "unknown",
        "workload_pattern": "periodic",
        "constraints": {
          "execution_constraint": "flexible",
          "deployment_role": "service",
          "binding_characteristics": [],
          "required_hardware_or_platform": [
            "Durable storage for historical data (component cloud_storage; technology not stated)"
          ]
        },
        "evidence": {
          "observed_facts": [
            "The cloud_storage component stores historical agricultural data."
          ],
          "inferred_characteristics": [
            "It appends records produced by the analysis stage.",
            "Stored volume grows with operating time.",
            "Read access patterns for the history are not stated."
          ]
        },
        "cpu": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "One crop-condition result and one stored history record are each about 0.1 kB."
          ],
          "typical_cores": 0.01,
          "peak_cores": 0.1,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "One small write every 10 s. The peak covers queries over the historical data, whose frequency is not stated."
        },
        "memory": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "One crop-condition result and one stored history record are each about 0.1 kB."
          ],
          "typical_gb": 0.05,
          "peak_gb": 0.1,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Write buffers and index/cache structures of the store. The peak covers queries over historical data."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "inferred",
          "assumption_refs": [],
          "memory_gb": 0,
          "basis": "Storing historical data involves no model or accelerated computation."
        },
        "storage": {
          "level": "low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "One crop-condition result and one stored history record are each about 0.1 kB.",
            "Historical data is retained for one year, with a storage overhead factor of about 2."
          ],
          "size_gb": 0.5,
          "persistent": true,
          "growth": "grows_over_time",
          "basis": "0.1 kB every 10 s is about 0.86 MB per day and about 0.32 GB per year of raw records. With an overhead factor of about 2, one year of retention is about 0.6 GB. That the store is persistent and grows is inferred from 'stores historical agricultural data', while the size is assumed."
        },
        "network": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "One sample is taken every 10 s (0.1 samples/s).",
            "One crop-condition result and one stored history record are each about 0.1 kB."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 8e-06,
          "potential_egress_mbps": 0,
          "basis": "Potential ingress is U2 -> U4 (0.000008, boundary unknown). The unit graph has no outgoing edge from this unit, so reads of the historical data are not modelled."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [],
        "how_to_measure": "Record the storage size growth over a week of operation and the number of writes per hour, and monitor the store's CPU and memory with its own metrics while running typical historical queries."
      }
    ],
    "communication_requirements": [
      {
        "source": "U1",
        "target": "U2",
        "payload": "Soil moisture and temperature samples",
        "flow_path": [
          "U1",
          "U2"
        ],
        "current_mechanism": "unknown",
        "boundary": "unknown",
        "message_size_kb": 0.05,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 0.1,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "One sample is taken every 10 s (0.1 samples/s).",
          "One soil-moisture and temperature sample with timestamp is about 0.05 kB."
        ],
        "bandwidth_mbps": 4e-06,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "unknown",
          "reason": "No explicit latency requirement in the input"
        },
        "basis": "0.05 x 0.1 x 8 / 1000 = 0.000004 Mbps."
      },
      {
        "source": "U2",
        "target": "U3",
        "payload": "Crop-condition analysis results",
        "flow_path": [
          "U2",
          "U3"
        ],
        "current_mechanism": "unknown",
        "boundary": "unknown",
        "message_size_kb": 0.1,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 0.1,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "One sample is taken every 10 s (0.1 samples/s).",
          "One crop-condition result and one stored history record are each about 0.1 kB."
        ],
        "bandwidth_mbps": 8e-06,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "unknown",
          "reason": "No explicit latency requirement in the input"
        },
        "basis": "One result per sample: 0.1 x 0.1 x 8 / 1000 = 0.000008 Mbps."
      },
      {
        "source": "U2",
        "target": "U4",
        "payload": "Measurement and crop-condition records for the historical data store",
        "flow_path": [
          "U2",
          "U4"
        ],
        "current_mechanism": "unknown",
        "boundary": "unknown",
        "message_size_kb": 0.1,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 0.1,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "One sample is taken every 10 s (0.1 samples/s).",
          "One crop-condition result and one stored history record are each about 0.1 kB."
        ],
        "bandwidth_mbps": 8e-06,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "low",
          "reason": "The target stores historical agricultural data, which needs only eventual delivery."
        },
        "basis": "One record per sample: 0.1 x 0.1 x 8 / 1000 = 0.000008 Mbps."
      }
    ],
    "summary": {
      "number_of_units": 4,
      "current_platform_load": [
        {
          "platform": "unknown",
          "runtime_units": [
            "U1",
            "U2",
            "U3",
            "U4"
          ],
          "application_cores": null,
          "application_memory_gb": null,
          "baseline_cores": null,
          "baseline_memory_gb": null,
          "combined_cores": null,
          "combined_memory_gb": null,
          "storage_gb": null,
          "units_without_numeric_values": [
            "U1"
          ],
          "provenance": "unknown"
        }
      ],
      "initialization_demand": {
        "units": [],
        "peak_cores": 0,
        "peak_memory_gb": 0,
        "persistent_storage_gb": 0,
        "startup_duration_s": null
      },
      "units_requiring_gpu": [],
      "physical_boundaries": [],
      "provenance_overview": {
        "estimates_by_provenance": {
          "observed": 0,
          "inferred": 7,
          "assumed": 13,
          "unknown": 0
        },
        "edges_by_bandwidth_provenance": {
          "observed": 0,
          "inferred": 0,
          "assumed": 3,
          "unknown": 0
        },
        "key_assumptions": [
          "One sample is taken every 10 s (0.1 samples/s).",
          "One crop-condition result and one stored history record are each about 0.1 kB.",
          "Crop analysis is rule-based or statistical; the input names no ML model."
        ]
      },
      "resource_observations": [
        "No estimate is observed: the input states no platform, sensor model, sampling rate, analysis method or data format. 13 of 20 estimates and all 3 edge bandwidths are assumed, mainly from the 10 s sampling interval and the record sizes.",
        "The 7 inferred estimates are qualitative: the absence of a GPU need and of local storage where the input describes none, and the very_low CPU and memory levels of U1 (reading two sensor values), whose numbers are null because its platform may be a microcontroller.",
        "Under the assumptions, all units are very_low for CPU, memory and network. U4 is the only unit with persistent, growing storage (low, about 0.5 GB for one year).",
        "The very_low CPU of U2 depends on the assumption that crop analysis uses no ML model. If a model is used, U2's CPU, memory and GPU estimates must be revised.",
        "Platform load is null because the input does not state which platform each unit uses or whether units share one.",
        "All three edges have unknown mechanism and boundary, so no edge is known to cross a physical link. Potential traffic is at most 0.000016 Mbps (U2 egress), and all of it scales linearly with the assumed sampling rate.",
        "The unit graph has no outgoing edges from U3 or U4, so the destination of irrigation decisions and reads of the historical data are not represented."
      ]
    },
    "calibration_status": "uncalibrated"
  }
}
```
