<!-- AUTO-GENERATED from prompt.md + input/smart_surveillance.json. Copy ALL of this file into the LLM chat. Save the reply as output/smart_surveillance.json. Do not edit. -->

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
  },
  "resource_estimation": {
    "application_id": "smart_surveillance",
    "estimation_method": "heuristic_llm",
    "assumptions": [
      "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB.",
      "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
      "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw.",
      "Object detection runs on the 640x360 frames, on every processed frame.",
      "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected.",
      "Frames are passed between units as uncompressed arrays inside the same Python program.",
      "All units are components of one Streamlit Python application on the operator's machine, so every unit-graph edge is currently an in-process call.",
      "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total).",
      "Models are downloaded at about 50 Mbps on first start; later starts use the local cache.",
      "Operator control actions occur about once every 100 s (0.01 per second), with about 0.1 kB each.",
      "Classification results, alerts and log records are about 0.2 kB each.",
      "Log files are retained for about one week.",
      "Frames are 8-bit RGB (3 bytes per pixel).",
      "The network level of a unit is based on the larger of its potential ingress and potential egress.",
      "The transfer of rendered frames from the Streamlit server to the browser front end happens inside U1 and is not a unit-graph edge."
    ],
    "platform_baselines": [
      {
        "platform": "Streamlit Python application process (operator's machine)",
        "units": [
          "U1",
          "U2",
          "U3",
          "U4",
          "U5",
          "U6",
          "U7"
        ],
        "cpu_cores": 0.1,
        "memory_gb": 1,
        "basis": "The Python interpreter, Streamlit server and script re-run loop, plus the imported PyTorch, Ultralytics, PyTorchVideo, Hugging Face Transformers, OpenCV and CUDA runtime libraries (host side). A CUDA context also occupies GPU memory once per process, which is not included in the unit GPU figures. The browser rendering the Streamlit front end is a separate process and is not included.",
        "confidence": "low"
      }
    ],
    "resource_profiles": [
      {
        "unit_id": "U1",
        "name": "Operator Interface",
        "unit_type": "runtime",
        "platform": "Streamlit Python application",
        "workload_pattern": "continuous",
        "constraints": {
          "execution_constraint": "device_bound",
          "deployment_role": "service",
          "binding_characteristics": [
            "hardware_access",
            "user_interaction"
          ],
          "required_hardware_or_platform": [
            "Streamlit dashboard (operator interface)",
            "Local machine speaker (optional beep)"
          ]
        },
        "evidence": {
          "observed_facts": [
            "The Streamlit dashboard lets the operator select the video source, set frame-skip, resolution and alert options, and start or stop detection.",
            "Video display renders the annotated frames, the current detection status and FPS statistics in the user interface.",
            "Alert notification raises a real-time status message and optional beep on the local machine speaker when a crime is detected."
          ],
          "inferred_characteristics": [
            "It receives display-resolution frames continuously from U3 and U5 and must render them for the operator.",
            "It receives small status and alert messages from U6.",
            "Control actions are sparse, operator-triggered events."
          ]
        },
        "cpu": {
          "level": "low",
          "provenance": "assumed",
          "assumption_refs": [
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw."
          ],
          "typical_cores": 0.25,
          "peak_cores": 0.5,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Encoding and pushing 640x360 frames to the Streamlit front end at about 15 FPS, plus updating the status text and FPS statistics. The peak covers alert handling and option changes that trigger script re-runs. The Streamlit baseline is excluded."
        },
        "memory": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw."
          ],
          "typical_gb": 0.05,
          "peak_gb": 0.05,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "A few display-resolution frames and their encoded copies, plus widget state."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "inferred",
          "assumption_refs": [],
          "memory_gb": 0,
          "basis": "UI rendering, text updates and a beep. No model inference."
        },
        "storage": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "size_gb": 0,
          "persistent": false,
          "growth": "none",
          "basis": "The input describes no data written by these components."
        },
        "network": {
          "level": "very_high",
          "provenance": "assumed",
          "assumption_refs": [
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw.",
            "Frames are passed between units as uncompressed arrays inside the same Python program.",
            "Classification results, alerts and log records are about 0.2 kB each.",
            "Operator control actions occur about once every 100 s (0.01 per second), with about 0.1 kB each."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 165.6016,
          "potential_egress_mbps": 8e-06,
          "basis": "Potential ingress is U3 -> U1 (82.8) + U5 -> U1 (82.8) + U6 -> U1 (0.0016). Potential egress is U1 -> U2 (0.000008). All edges are logical in-process calls, so physical traffic is 0."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [
          "Both the preprocessed frame stream (U3) and the annotated frame stream (U5) reach the display at 15 FPS, as the graph has both edges."
        ],
        "how_to_measure": "Profile the Streamlit process with py-spy during detection, attributing samples to st.image and UI update calls, and measure RSS with psutil while the display runs at the configured resolution and frame skip."
      },
      {
        "unit_id": "U2",
        "name": "Video Acquisition",
        "unit_type": "runtime",
        "platform": "Streamlit Python application",
        "workload_pattern": "continuous",
        "constraints": {
          "execution_constraint": "device_bound",
          "deployment_role": "service",
          "binding_characteristics": [
            "hardware_access"
          ],
          "required_hardware_or_platform": [
            "Local webcam (or an uploaded video file)"
          ]
        },
        "evidence": {
          "observed_facts": [
            "Captures frames continuously from the local webcam, or reads them from an uploaded video file, at the target FPS."
          ],
          "inferred_characteristics": [
            "A continuous stream of full-resolution frames is produced for preprocessing.",
            "Webcam capture or file decoding runs on every source frame, before frame skipping."
          ]
        },
        "cpu": {
          "level": "low",
          "provenance": "assumed",
          "assumption_refs": [
            "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB."
          ],
          "typical_cores": 0.25,
          "peak_cores": 0.5,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Grabbing and decoding 1280x720 frames at 30 FPS from the webcam. The peak covers decoding a compressed uploaded video file."
        },
        "memory": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB."
          ],
          "typical_gb": 0.01,
          "peak_gb": 0.01,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Capture buffers holding a few raw 1280x720 frames."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "inferred",
          "assumption_refs": [],
          "memory_gb": 0,
          "basis": "Frame capture and decoding only."
        },
        "storage": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "size_gb": 0,
          "persistent": false,
          "growth": "none",
          "basis": "Frames are not stored. The size of an uploaded video file is not stated in the input and is not counted."
        },
        "network": {
          "level": "very_high",
          "provenance": "assumed",
          "assumption_refs": [
            "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB.",
            "Frames are passed between units as uncompressed arrays inside the same Python program.",
            "Operator control actions occur about once every 100 s (0.01 per second), with about 0.1 kB each."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 8e-06,
          "potential_egress_mbps": 672,
          "basis": "Potential ingress is U1 -> U2 control (0.000008). Potential egress is U2 -> U3 raw frames (672). Both edges are logical."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [],
        "how_to_measure": "Time the capture/read call per frame and record the achieved FPS, and measure the capture thread's CPU share with py-spy and psutil for both webcam and uploaded-file sources."
      },
      {
        "unit_id": "U3",
        "name": "Frame Preprocessing",
        "unit_type": "runtime",
        "platform": "Streamlit Python application",
        "workload_pattern": "continuous",
        "constraints": {
          "execution_constraint": "flexible",
          "deployment_role": "service",
          "binding_characteristics": [],
          "required_hardware_or_platform": []
        },
        "evidence": {
          "observed_facts": [
            "Resizes frames to the selected display resolution, applies frame skipping, and produces 224x224 frames for action recognition."
          ],
          "inferred_characteristics": [
            "It receives every source frame, keeps one in N, and produces two resized versions per processed frame.",
            "It is stateless apart from the frame-skip counter."
          ]
        },
        "cpu": {
          "level": "low",
          "provenance": "assumed",
          "assumption_refs": [
            "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB.",
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw."
          ],
          "typical_cores": 0.25,
          "peak_cores": 0.5,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Two image resizes (to the display resolution and to 224x224) for 15 processed frames per second, plus skip logic on 30 incoming frames per second. The peak covers a higher display resolution or no frame skipping."
        },
        "memory": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB.",
            "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw."
          ],
          "typical_gb": 0.01,
          "peak_gb": 0.01,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "One input frame and two resized output frames in flight."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "inferred",
          "assumption_refs": [],
          "memory_gb": 0,
          "basis": "Image resizing and frame skipping only."
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
          "level": "very_high",
          "provenance": "assumed",
          "assumption_refs": [
            "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB.",
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw.",
            "Frames are passed between units as uncompressed arrays inside the same Python program.",
            "Frames are 8-bit RGB (3 bytes per pixel)."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 672,
          "potential_egress_mbps": 183.6,
          "basis": "Potential ingress is U2 -> U3 (672). Potential egress is U3 -> U1 (82.8) + U3 -> U5 (82.8) + U3 -> U6 (18). All edges are logical."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [],
        "how_to_measure": "Time the resize and skip code per frame with time.perf_counter() under the configured resolution and frame skip, and check memory with tracemalloc."
      },
      {
        "unit_id": "U4",
        "name": "Model Provisioning",
        "unit_type": "initialization",
        "platform": "Streamlit Python application",
        "workload_pattern": "startup_only",
        "constraints": {
          "execution_constraint": "flexible",
          "deployment_role": "dependency",
          "binding_characteristics": [
            "external_service_dependency"
          ],
          "required_hardware_or_platform": [
            "Hugging Face model hub",
            "PyTorchVideo model repository"
          ]
        },
        "evidence": {
          "observed_facts": [
            "Downloads pretrained models from Hugging Face and PyTorchVideo (YOLOv8-large, VideoMAE crime detector, I3D-R50) and loads them into CPU/GPU memory at startup."
          ],
          "inferred_characteristics": [
            "A one-time download of three model files, followed by deserialization and transfer into CPU or GPU memory.",
            "Once loaded, the models are held by the inference units U5 and U6."
          ]
        },
        "cpu": {
          "level": "medium",
          "provenance": "assumed",
          "assumption_refs": [
            "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total)."
          ],
          "typical_cores": 1,
          "peak_cores": 2,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Download handling, checkpoint deserialization and model construction at startup. The peak occurs while weights are unpickled and copied to the device."
        },
        "memory": {
          "level": "medium",
          "provenance": "assumed",
          "assumption_refs": [
            "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total)."
          ],
          "typical_gb": 0.5,
          "peak_gb": 1,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Transient host copies of about 540 MB of checkpoints during loading. The resident models after loading are counted in U5 and U6, not here."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "inferred",
          "assumption_refs": [],
          "memory_gb": 0,
          "basis": "The unit only transfers weights. The GPU memory they occupy afterwards is counted in U5 and U6."
        },
        "storage": {
          "level": "low",
          "provenance": "assumed",
          "assumption_refs": [
            "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total)."
          ],
          "size_gb": 0.5,
          "persistent": true,
          "growth": "none",
          "basis": "The cached model files (about 540 MB total) stay on disk for later starts. U5 and U6 do not count this storage again."
        },
        "network": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 0,
          "potential_egress_mbps": 0,
          "basis": "Its unit-graph edges (U4 -> U5, U4 -> U6) are startup_only with 0 bandwidth by definition. The one-time download from the model repositories is not a unit-graph edge and is reflected in startup_duration_s."
        },
        "transient": true,
        "startup_duration_s": 100,
        "confidence": "low",
        "assumptions": [
          "The first start downloads about 540 MB at 50 Mbps (about 86 s) plus about 15 s of loading. With a warm cache, startup is about 15 s. This relies on 'Models are downloaded at about 50 Mbps on first start; later starts use the local cache.'"
        ],
        "how_to_measure": "Time the model loader from process start to the first inference-ready state with and without a warm cache, record peak RSS with psutil, and check the size of the Hugging Face and torch hub cache directories."
      },
      {
        "unit_id": "U5",
        "name": "Object Detection and Tracking",
        "unit_type": "runtime",
        "platform": "Streamlit Python application",
        "workload_pattern": "continuous",
        "constraints": {
          "execution_constraint": "flexible",
          "deployment_role": "service",
          "binding_characteristics": [],
          "required_hardware_or_platform": [
            "Pretrained YOLOv8-large model (provided by U4)",
            "DeepSORT tracker with MobileNet appearance embedder"
          ]
        },
        "evidence": {
          "observed_facts": [
            "Runs YOLOv8-large deep learning inference on each sent frame to detect objects and people with confidence above 0.5.",
            "Applies DeepSORT tracking with a MobileNet appearance embedder to assign persistent IDs to detections and draws labeled bounding boxes on the frame.",
            "The model loader loads models into CPU/GPU memory."
          ],
          "inferred_characteristics": [
            "Large-detector inference on every processed frame.",
            "Per-detection appearance embedding and track association, with track state kept across frames.",
            "One annotated frame is produced per processed frame."
          ]
        },
        "cpu": {
          "level": "medium",
          "provenance": "assumed",
          "assumption_refs": [
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "Object detection runs on the 640x360 frames, on every processed frame."
          ],
          "typical_cores": 1,
          "peak_cores": 2,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "With the GPU: host-side pre/post-processing, NMS, DeepSORT association, embedding scheduling and box drawing at 15 FPS. The peak covers scenes with many detections. Without a GPU, YOLOv8-large inference moves to the CPU. The need then grows to more than 8 cores and still falls well short of 15 FPS."
        },
        "memory": {
          "level": "medium",
          "provenance": "assumed",
          "assumption_refs": [
            "Object detection runs on the 640x360 frames, on every processed frame.",
            "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total)."
          ],
          "typical_gb": 0.5,
          "peak_gb": 1,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Host-side YOLOv8-large and MobileNet model objects, frame tensors, DeepSORT track state and appearance features. The Python/PyTorch baseline is excluded."
        },
        "gpu": {
          "requirement": "required",
          "provenance": "assumed",
          "assumption_refs": [
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "Object detection runs on the 640x360 frames, on every processed frame."
          ],
          "memory_gb": 2,
          "basis": "YOLOv8-large weights, activations for the detection input and the MobileNet embedder. That this is a large detector running on each sent frame is observed. That a GPU is required rather than optional follows from the assumed 15 FPS rate, since the input indicates a CPU fallback exists, but only at a much lower frame rate."
        },
        "storage": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "size_gb": 0,
          "persistent": false,
          "growth": "none",
          "basis": "Model files are counted in U4. Nothing else is stored."
        },
        "network": {
          "level": "high",
          "provenance": "assumed",
          "assumption_refs": [
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw.",
            "Frames are passed between units as uncompressed arrays inside the same Python program."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 82.8,
          "potential_egress_mbps": 82.8,
          "basis": "Potential ingress is U3 -> U5 (82.8). Potential egress is U5 -> U1 (82.8). U4 -> U5 is startup_only with 0 bandwidth. All edges are logical."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [],
        "how_to_measure": "Profile CPU and RSS of the detection/tracking code with psutil and py-spy, and GPU memory and utilization with nvidia-smi, while processing a 30 FPS 720p video with frame skip 2. Repeat with a CPU-only run to confirm the fallback frame rate."
      },
      {
        "unit_id": "U6",
        "name": "Crime and Activity Recognition",
        "unit_type": "runtime",
        "platform": "Streamlit Python application",
        "workload_pattern": "continuous",
        "constraints": {
          "execution_constraint": "flexible",
          "deployment_role": "service",
          "binding_characteristics": [],
          "required_hardware_or_platform": [
            "Pretrained VideoMAE crime detector and I3D-R50 (Kinetics-400) models (provided by U4)"
          ]
        },
        "evidence": {
          "observed_facts": [
            "Keeps a sliding buffer of the last 16 sampled frames used as the input clip for crime detection.",
            "Runs a VideoMAE video classification model on the 16-frame clip to classify the scene as crime or no crime.",
            "When no crime is detected, runs the pretrained I3D-R50 model on the same clip to label the ongoing normal activity."
          ],
          "inferred_characteristics": [
            "The buffer is updated on every sampled 224x224 frame.",
            "Video-transformer inference on a 16x224x224 clip, followed in the no-crime case by 3D-CNN inference on the same clip.",
            "Outputs are small classification labels and alerts."
          ]
        },
        "cpu": {
          "level": "low",
          "provenance": "assumed",
          "assumption_refs": [
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected."
          ],
          "typical_cores": 0.25,
          "peak_cores": 1,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "With the GPU: buffer updates at 15 frames per second, plus clip normalization and tensor preparation once per second. The peak occurs when both models run on the same clip. Without a GPU, each VideoMAE plus I3D-R50 pass on a 16-frame clip takes several seconds on 4 or more cores, so one classification per second could not be sustained."
        },
        "memory": {
          "level": "medium",
          "provenance": "assumed",
          "assumption_refs": [
            "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total).",
            "Frames are 8-bit RGB (3 bytes per pixel)."
          ],
          "typical_gb": 0.5,
          "peak_gb": 1,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Host-side VideoMAE and I3D-R50 model objects, the 16-frame buffer (about 2.4 MB) and clip tensors. The Python/PyTorch baseline is excluded."
        },
        "gpu": {
          "requirement": "required",
          "provenance": "assumed",
          "assumption_refs": [
            "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected.",
            "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total)."
          ],
          "memory_gb": 2,
          "basis": "VideoMAE and I3D-R50 weights plus activations for a 16x224x224 clip. The two named video models are observed. That a GPU is required rather than optional follows from the assumed classification rate, since the input indicates a CPU fallback exists, but at a much lower rate."
        },
        "storage": {
          "level": "very_low",
          "provenance": "inferred",
          "assumption_refs": [],
          "size_gb": 0,
          "persistent": false,
          "growth": "none",
          "basis": "Model files are counted in U4. The frame buffer is held in memory."
        },
        "network": {
          "level": "high",
          "provenance": "assumed",
          "assumption_refs": [
            "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
            "Frames are 8-bit RGB (3 bytes per pixel).",
            "Frames are passed between units as uncompressed arrays inside the same Python program.",
            "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected.",
            "Classification results, alerts and log records are about 0.2 kB each."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 18,
          "potential_egress_mbps": 0.0032,
          "basis": "Potential ingress is U3 -> U6 (18). Potential egress is U6 -> U1 (0.0016) + U6 -> U7 (0.0016). U4 -> U6 is startup_only with 0 bandwidth. All edges are logical."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [],
        "how_to_measure": "Log the timestamps of each crime/activity inference to obtain the real classification rate, and profile CPU and RSS with psutil and GPU memory with nvidia-smi during a video that contains both crime and normal scenes."
      },
      {
        "unit_id": "U7",
        "name": "Event Logging",
        "unit_type": "runtime",
        "platform": "Streamlit Python application",
        "workload_pattern": "event_driven",
        "constraints": {
          "execution_constraint": "flexible",
          "deployment_role": "service",
          "binding_characteristics": [],
          "required_hardware_or_platform": [
            "File system with a logs folder"
          ]
        },
        "evidence": {
          "observed_facts": [
            "Writes timestamped detection results, crime events and system events to log files in the logs folder."
          ],
          "inferred_characteristics": [
            "Small text records are appended for every classification result and event.",
            "Log volume grows with running time."
          ]
        },
        "cpu": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected.",
            "Classification results, alerts and log records are about 0.2 kB each."
          ],
          "typical_cores": 0.01,
          "peak_cores": 0.01,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Formatting and appending about one short record per second. The actual demand is below the smallest grid value."
        },
        "memory": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "Classification results, alerts and log records are about 0.2 kB each."
          ],
          "typical_gb": 0.001,
          "peak_gb": 0.001,
          "native_estimate": null,
          "not_comparable_reason": null,
          "basis": "Log handler buffers. The actual demand is below the smallest grid value."
        },
        "gpu": {
          "requirement": "none",
          "provenance": "inferred",
          "assumption_refs": [],
          "memory_gb": 0,
          "basis": "File writes only."
        },
        "storage": {
          "level": "low",
          "provenance": "assumed",
          "assumption_refs": [
            "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected.",
            "Classification results, alerts and log records are about 0.2 kB each.",
            "Log files are retained for about one week."
          ],
          "size_gb": 0.1,
          "persistent": true,
          "growth": "grows_over_time",
          "basis": "About 0.2 kB per second is about 17 MB per day, so one week of retention is about 0.12 GB. That the logs are persistent and grow is observed from the function, while the size is assumed. Without rotation, size grows without bound."
        },
        "network": {
          "level": "very_low",
          "provenance": "assumed",
          "assumption_refs": [
            "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected.",
            "Classification results, alerts and log records are about 0.2 kB each."
          ],
          "physical_ingress_mbps": 0,
          "physical_egress_mbps": 0,
          "potential_ingress_mbps": 0.0016,
          "potential_egress_mbps": 0,
          "basis": "Potential ingress is U6 -> U7 (0.0016). The edge is logical."
        },
        "transient": false,
        "startup_duration_s": null,
        "confidence": "low",
        "assumptions": [],
        "how_to_measure": "Monitor the size growth of the logs folder over a 24-hour run, and count records per minute."
      }
    ],
    "communication_requirements": [
      {
        "source": "U1",
        "target": "U2",
        "payload": "Operator control: selected video source, start/stop detection",
        "flow_path": [
          "U1",
          "U2"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 0.1,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 0.01,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "Operator control actions occur about once every 100 s (0.01 per second), with about 0.1 kB each.",
          "All units are components of one Streamlit Python application on the operator's machine, so every unit-graph edge is currently an in-process call."
        ],
        "bandwidth_mbps": 8e-06,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "medium",
          "reason": "The operator starts and stops detection and selects the source, which is an operator command requiring seconds-scale responsiveness."
        },
        "basis": "0.1 x 0.01 x 8 / 1000 = 0.000008 Mbps, the load if the units were separated."
      },
      {
        "source": "U2",
        "target": "U3",
        "payload": "Raw 1280x720 RGB frames from the webcam or video file",
        "flow_path": [
          "U2",
          "U3"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 2800,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 30,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB.",
          "Frames are passed between units as uncompressed arrays inside the same Python program.",
          "All units are components of one Streamlit Python application on the operator's machine, so every unit-graph edge is currently an in-process call."
        ],
        "bandwidth_mbps": 672,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "high",
          "reason": "Frames are captured continuously at the target FPS, and each frame feeds the real-time display and detection path."
        },
        "basis": "2800 x 30 x 8 / 1000 = 672 Mbps of raw arrays, before frame skipping."
      },
      {
        "source": "U3",
        "target": "U1",
        "payload": "Resized display-resolution frames",
        "flow_path": [
          "U3",
          "U1"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 690,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 15,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw.",
          "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
          "Frames are passed between units as uncompressed arrays inside the same Python program."
        ],
        "bandwidth_mbps": 82.8,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "high",
          "reason": "Frames are sent on every processed frame for live rendering."
        },
        "basis": "690 x 15 x 8 / 1000 = 82.8 Mbps."
      },
      {
        "source": "U3",
        "target": "U5",
        "payload": "Resized display-resolution frames for object detection",
        "flow_path": [
          "U3",
          "U5"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 690,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 15,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw.",
          "Object detection runs on the 640x360 frames, on every processed frame.",
          "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
          "Frames are passed between units as uncompressed arrays inside the same Python program."
        ],
        "bandwidth_mbps": 82.8,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "high",
          "reason": "Detection runs on each sent frame, and its annotated output feeds the live display."
        },
        "basis": "690 x 15 x 8 / 1000 = 82.8 Mbps."
      },
      {
        "source": "U3",
        "target": "U6",
        "payload": "224x224 RGB frames for the crime-detection sliding buffer",
        "flow_path": [
          "U3",
          "U6"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 150,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 15,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "Frames are 8-bit RGB (3 bytes per pixel).",
          "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
          "Frames are passed between units as uncompressed arrays inside the same Python program."
        ],
        "bandwidth_mbps": 18,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "high",
          "reason": "Each sampled frame updates the clip that drives the real-time crime alert."
        },
        "basis": "The 224x224 size is observed. At 3 bytes per pixel a frame is about 150 kB: 150 x 15 x 8 / 1000 = 18 Mbps."
      },
      {
        "source": "U4",
        "target": "U5",
        "payload": "One-time loading of the YOLOv8-large model",
        "flow_path": [
          "U4",
          "U5"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 0,
        "message_size_provenance": "inferred",
        "message_rate_per_s": 0,
        "message_rate_provenance": "inferred",
        "bandwidth_provenance": "inferred",
        "assumption_refs": [
          "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total)."
        ],
        "bandwidth_mbps": 0,
        "one_time_transfer_mb": 84,
        "latency_sensitivity": {
          "level": "not_applicable",
          "reason": "Startup-only initialization transfer."
        },
        "basis": "The model is loaded at startup, so the rate and bandwidth are 0 by definition. The one-time volume (about 84 MB) is assumed."
      },
      {
        "source": "U4",
        "target": "U6",
        "payload": "One-time loading of the VideoMAE crime detector and I3D-R50 models",
        "flow_path": [
          "U4",
          "U6"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 0,
        "message_size_provenance": "inferred",
        "message_rate_per_s": 0,
        "message_rate_provenance": "inferred",
        "bandwidth_provenance": "inferred",
        "assumption_refs": [
          "Model file sizes are general-knowledge estimates: YOLOv8-large about 84 MB, VideoMAE crime detector about 350 MB, I3D-R50 about 110 MB (about 540 MB in total)."
        ],
        "bandwidth_mbps": 0,
        "one_time_transfer_mb": 460,
        "latency_sensitivity": {
          "level": "not_applicable",
          "reason": "Startup-only initialization transfer."
        },
        "basis": "The models are loaded at startup, so the rate and bandwidth are 0 by definition. The one-time volume (about 350 + 110 MB) is assumed."
      },
      {
        "source": "U5",
        "target": "U1",
        "payload": "Annotated frames with labeled bounding boxes and track IDs",
        "flow_path": [
          "U5",
          "U1"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 690,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 15,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw.",
          "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
          "Frames are passed between units as uncompressed arrays inside the same Python program."
        ],
        "bandwidth_mbps": 82.8,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "high",
          "reason": "An annotated frame is produced on every processed frame for the live view."
        },
        "basis": "690 x 15 x 8 / 1000 = 82.8 Mbps."
      },
      {
        "source": "U6",
        "target": "U1",
        "payload": "Crime / no-crime status, normal-activity label and crime alert events",
        "flow_path": [
          "U6",
          "U1"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 0.2,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 1,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "Classification results, alerts and log records are about 0.2 kB each.",
          "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected."
        ],
        "bandwidth_mbps": 0.0016,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "high",
          "reason": "The input describes a real-time alert raised when a crime is detected."
        },
        "basis": "0.2 x 1 x 8 / 1000 = 0.0016 Mbps. Alerts are included in this rate."
      },
      {
        "source": "U6",
        "target": "U7",
        "payload": "Timestamped detection results and crime events for the log files",
        "flow_path": [
          "U6",
          "U7"
        ],
        "current_mechanism": "in_process_call",
        "boundary": "logical",
        "message_size_kb": 0.2,
        "message_size_provenance": "assumed",
        "message_rate_per_s": 1,
        "message_rate_provenance": "assumed",
        "bandwidth_provenance": "assumed",
        "assumption_refs": [
          "Classification results, alerts and log records are about 0.2 kB each.",
          "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected."
        ],
        "bandwidth_mbps": 0.0016,
        "one_time_transfer_mb": null,
        "latency_sensitivity": {
          "level": "low",
          "reason": "Log records need only eventual delivery."
        },
        "basis": "0.2 x 1 x 8 / 1000 = 0.0016 Mbps."
      }
    ],
    "summary": {
      "number_of_units": 7,
      "current_platform_load": [
        {
          "platform": "Streamlit Python application process (operator's machine)",
          "runtime_units": [
            "U1",
            "U2",
            "U3",
            "U5",
            "U6",
            "U7"
          ],
          "application_cores": 2.01,
          "application_memory_gb": 1.071,
          "baseline_cores": 0.1,
          "baseline_memory_gb": 1,
          "combined_cores": 2.11,
          "combined_memory_gb": 2.071,
          "storage_gb": 0.1,
          "units_without_numeric_values": [],
          "provenance": "assumed"
        }
      ],
      "initialization_demand": {
        "units": [
          "U4"
        ],
        "peak_cores": 2,
        "peak_memory_gb": 1,
        "persistent_storage_gb": 0.5,
        "startup_duration_s": 100
      },
      "units_requiring_gpu": [
        "U5",
        "U6"
      ],
      "physical_boundaries": [],
      "provenance_overview": {
        "estimates_by_provenance": {
          "observed": 0,
          "inferred": 11,
          "assumed": 24,
          "unknown": 0
        },
        "edges_by_bandwidth_provenance": {
          "observed": 0,
          "inferred": 2,
          "assumed": 8,
          "unknown": 0
        },
        "key_assumptions": [
          "The webcam delivers 1280x720 RGB frames at 30 FPS; one raw frame is about 2800 kB.",
          "Frame skipping processes every 2nd frame, giving 15 processed frames per second.",
          "The selected display resolution is 640x360; one display or detection frame is about 690 kB raw.",
          "Crime detection classifies the 16-frame clip about once per second; activity recognition runs on the same clip when no crime is detected.",
          "Frames are passed between units as uncompressed arrays inside the same Python program."
        ]
      },
      "resource_observations": [
        "The named models (YOLOv8-large, VideoMAE, I3D-R50), the per-frame and per-clip inference and the 224x224 clip size are observed, so the kind of demand is well founded. Every numeric CPU, memory, GPU and bandwidth value still depends on the assumed camera resolution, frame rate, frame skip, display resolution and classification rate. This is why 24 of 35 estimates are assumed and every unit has low confidence.",
        "The 11 inferred estimates are qualitative: no GPU need for UI, capture, preprocessing, model loading and logging; no storage in units that write nothing; and 0 bandwidth on startup-only edges.",
        "U5 accounts for about half of the estimated application CPU (1 of 2.01 cores). U1, U2, U3 and U6 are low (0.25 cores each), and U7 is very_low.",
        "U5 and U6 hold almost all application host memory (0.5 GB each of 1.071 GB) and all GPU demand (2 GB each, plus the per-process CUDA context). Whether a GPU is required rather than optional depends on the assumed 15 FPS and 1 clip/s rates.",
        "The raw frame flows are the largest communication volumes: U2 -> U3 at 672 Mbps, and U3 -> U1, U3 -> U5 and U5 -> U1 at 82.8 Mbps each. Clip frames U3 -> U6 carry 18 Mbps, while result, alert, log and control flows are at most 0.0016 Mbps. All frame values assume uncompressed arrays and would drop substantially with encoding.",
        "No edge crosses a physical device link today: all ten edges are logical in-process calls inside the Streamlit application.",
        "U4 needs about 0.5 GB of persistent model storage and a one-time download from the model repositories, estimated at about 100 s on first start. Its loaded models are counted in U5 and U6.",
        "U7 is the only runtime unit with persistent, growing storage (about 17 MB per day)."
      ]
    },
    "calibration_status": "uncalibrated"
  }
}
```
