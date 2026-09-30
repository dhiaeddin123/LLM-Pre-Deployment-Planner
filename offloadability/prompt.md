# Offloadability Analysis Prompt

<!--
TEMPLATE - do not paste anything into this file.
To run an application, use ready_prompts/<application>.md
(this template + input/<application>.json, which combines the functional graph,
the granularity output and the resource estimation output), copy ALL of it into
any LLM chat and save the JSON reply as output/<application>.json.
-->

=== PROMPT START ===

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
{{OFFLOADABILITY_INPUT_JSON}}
```
