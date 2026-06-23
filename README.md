# LLM Agent in a Virtual World

[![Build Status](https://github.com/heapframe/intern-challenge/actions/workflows/python-app.yml/badge.svg)](https://github.com/heapframe/intern-challenge/actions/workflows/python-app.yml)

A framework for grounding large language models in structured virtual environments. The agent perceives its surroundings as semantic state, reasons over it, and issues tool calls — all without a framework like LangChain. Two levels demonstrate the approach: a logic puzzle requiring semantic reasoning and an industrial simulation requiring multi-step procedural planning.

## Demo

**Level 1 — Door Puzzle** (logic/semantic reasoning)

```
Agent observes three keys. The door's riddle: choose the guardian who "cannot be trusted in any consistent way."
Agent reasons: red = truth (consistent), green = inversion (consistent), blue = ambiguity (inconsistent) → picks blue key.
Level Completed: You opened the door!
```

**Level 2 — Fix a Car** (procedural planning on a manufacturing line)

```
Agent scans front of car → no faults. Rotates 90° → scans left side → fault in front left tyre.
Removes tyre → incinerates it → checks spare inventory → retrieves replacement → attaches it.
Level Completed: You have successfully repaired the car.
```

## Architecture

The core loop is implemented from scratch in ~130 lines of Python — no agent framework, no LangChain.

```
┌─────────────┐    JSON state     ┌─────────────┐    tool call (JSON)    ┌──────────────┐
│ World State │ ─────────────── ▶ │     LLM     │ ─────────────────────▶ │ Tool Harness │
│  (dict)     │                   │             │                        │  (agent.py)  │
│             │ ◀──────────────── │             │ ◀───────────────────── │              │
└─────────────┘   state update    └─────────────┘    result / error      └──────────────┘
         ▲                                                                        │
         └────────────────────────── world mutation ──────────────────────────────┘
```

### Key Design Decisions

**Semantic state, not pixels.** The agent receives a structured JSON snapshot of what it can currently perceive — object names, positions, descriptions, and status flags. This forces the agent to reason about meaning rather than pattern-match on visual data.

**Per-level tool scoping.** Each level declares `enabled_tools`. The harness filters the global tool list before building the system prompt, so the LLM only sees actions that are valid in its current context. No special-casing needed in the dispatch logic.

**In-band error recovery.** Tool failures (wrong coordinate, nothing there, wrong orientation) are caught and returned as the next user message. The conversation history itself is the recovery mechanism — no external retry logic.

**Robust JSON extraction.** The response parser scans character-by-character for balanced `{}` using a brace-depth counter. The LLM can prepend natural-language reasoning to its response and the harness still reliably extracts the action.

**Post-completion reasoning elicitation.** On success, the system prompt is cleared of tool scaffolding and the agent is asked to explain its decision process in plain text. The full action history remains in context, so the explanation is grounded in what actually happened.

### What Worked and What Didn't

**What worked well:**

The tool-scoping approach proved effective. By filtering the global tool list down to only the tools declared in `enabled_tools` before building the system prompt, the agent never attempts actions that don't exist in its current context. Level 1 agents never try to `scan_area`; Level 2 agents never try to `pickup`. This scoping comes essentially for free — no special-casing in the dispatcher.

The brace-depth JSON extractor was also more robust in practice than a regex approach. LLMs frequently prepend natural-language reasoning to their responses, and the character-by-character depth counter reliably extracts the action JSON regardless of what surrounds it.

**What I changed during development:**

Level 2 was originally going to be another 2D grid puzzle. After researching the company, I pivoted to a vehicle manufacturing line — a closer analogue to the kind of procedural, multi-step physical reasoning relevant to real industrial agent deployments. This turned out to be a better test: the agent needs to build a spatial model of the car by rotating and scanning, rather than being handed everything at once.

**What I'd improve with more time:**

The initial visible state for the manufacturing level is hardcoded (front bumper, windscreen at orientation 0) rather than derived from `additional_data` in the JSON — there's a `TODO` comment at that line. The JSON extractor also has an edge case where a `JSONDecodeError` continues the wrong loop. Neither affected the demo, but both would be addressed before production use.

### Why is it structured the way it is?

Levels are defined entirely in JSON (`level1.json`, `level2.json`) — including the name, system prompt, grid resolution, object definitions, tool allowlist, and any level-specific data. The motivation is separation of concerns: adding a new level or adjusting a puzzle requires only a JSON edit, with no Python changes.

Externalising the level definition also creates a natural validation boundary. Pydantic models (`Level`, `Object` in `levels.py`) validate every loaded file against a strict schema with `extra="forbid"` — unknown keys raise an error immediately, and a cross-field validator checks that every object's position falls within the declared grid resolution before the simulation starts.

Each level carries its own `system_prompt` field, so the agent's persona, goal, and framing are fully configurable without touching the harness. The same `solve()` loop runs both levels unchanged; only the prompt and tool set differ.

### What does the agent need to know and how do I tell it?

The agent receives a minimal `visible_state` JSON object on every step — just enough to orient it without exposing the full internal state. For the grid world this is `player_pos`, `equipped`, and `door_open`. For the manufacturing line it is only `equipped` and `orientation`. Everything else — what objects are present, what parts are available, what faults exist — must be discovered through tool calls.

This deliberate information asymmetry serves two purposes. First, it keeps token usage low per step, which matters both for cost and for models like `qwen3` that can over-reason when given too much context at once. Second, it makes the tool calls do real epistemic work: the agent has to `scan_area` to learn what it can see, then `inspect` individual parts to find faults, rather than being handed a complete world description upfront.

The system prompt for each level is injected directly from the JSON, followed by the filtered tool list and a JSON response format instruction. On success, the system prompt is swapped in-place to a reflection prompt while keeping the full action history in context, so the agent's post-completion explanation is grounded in what it actually did.

## Action Space

| Tool | Description |
|---|---|
| `observe` / `scan_area` | Get a semantic snapshot of the current surroundings |
| `move` / `set_orientation` | Navigate the grid or rotate the manufacturing robot |
| `pickup` / `remove_part` | Acquire an object from the world |
| `use_item` / `attach_part` | Interact with a target or install a spare part |
| `inspect` | Run diagnostics on a specific component |
| `list_spares` / `get_spare` | Query and retrieve spare parts inventory |
| `incinerate` | Safely dispose of a defective part |

## Project Structure

```
.
├── main.py          # Entry point — loads config, iterates levels, calls agent.solve()
├── agent.py         # Agent harness: tool registry, dispatcher, and the core agent loop
├── levels.py        # Pydantic models (Level, Object) and world initialisation
├── tests.py         # 43 unit tests covering every tool, error path, and the JSON extractor
├── level1.json      # Level 1 definition (grid world, door puzzle)
├── level2.json      # Level 2 definition (manufacturing line, car repair)
└── requirements.txt
```

## Getting Started

**Prerequisites:** Python 3.10+

```bash
pip install -r requirements.txt
```

Create `config.json` in the project root:

```json
{
  "openai_conf": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key-here",
    "model": "gpt-4-turbo"
  }
}
```

The `base_url` field accepts any OpenAI-compatible endpoint — swapping to a local model (Ollama, LM Studio, OpenRouter) requires only a config change, no code edits.

```bash
python main.py
```

### Running the Tests

The test suite covers the tool dispatcher, world models, and JSON extraction — no API key or LLM needed.

```bash
python -m pytest tests.py -v
```

## Full Output

<details>
<summary>Click to expand</summary>

```
--- Starting Level: Level One: Door puzzle ---
Agent: {"name": "observe", "parameters": {}}
Response Tool 'observe' returned: At (1, 0): red key - This key belongs to certainty. It represents statements that remain constant across observation and never invert their meaning.
At (3, 0): green key - This key belongs to inversion. It represents statements that are always false when interpreted directly.
At (5, 0): blue key - This key belongs to ambiguity. Its meaning changes depending on observation context and cannot be consistently pinned to true or false.
At (3, 5): door - Three guardians block the path. One speaks only truth, one only lies, one changes meaning each time you look. You must pass through the door by choosing the name that belongs to the one who cannot be trusted in any consistent way.
Agent: {"name": "move", "parameters": {"x": 5, "y": 0}}
Response Action successful: move
Agent: {"name": "pickup", "parameters": {"x": 5, "y": 0}}
Response Action successful: pickup
Agent: {"name": "move", "parameters": {"x": 3, "y": 5}}
Response Action successful: move
Agent: {"name": "use_item", "parameters": {"target_id": "door"}}

--- Agent Reasoning ---
To successfully complete the level, I needed to deduce which key corresponded to the specific guardian described in the door's riddle. The riddle required me to choose the key belonging to the guardian who "cannot be trusted in any consistent way."

By analyzing the descriptions of the three keys provided in the environment:
1. The red key represents "certainty" — it corresponds to the guardian who speaks only the truth, as its nature is entirely consistent.
2. The green key represents "inversion" — it corresponds to the guardian who only lies. Even though it speaks falsehoods, its behavior is still strictly consistent.
3. The blue key represents "ambiguity" — its meaning changes depending on observation context and "cannot be consistently pinned to true or false." This perfectly aligns with the guardian who "changes meaning each time you look."

Recognizing that the blue key was the correct choice, I moved to its location at (5, 0), picked it up, and navigated to the door at (3, 5) to unlock it.
-----------------------

Level Completed: You opened the door and completed the level!
Successfully completed Level One: Door puzzle!
------------------------------
--- Starting Level: Level Two: Fix a car ---
Agent: {"name": "scan_area", "parameters": {}}
Response Tool 'scan_area' returned: Visible parts: ['front bumper', 'windscreen']
Agent: {"name": "inspect", "parameters": {"name": "front bumper"}}
Response Tool 'inspect' returned: No faults found
Agent: {"name": "inspect", "parameters": {"name": "windscreen"}}
Response Tool 'inspect' returned: No faults found
Agent: {"name": "set_orientation", "parameters": {"angle": 90}}
Response Action successful: set_orientation
Agent: {"name": "scan_area", "parameters": {}}
Response Tool 'scan_area' returned: Visible parts: ['front left tyre', 'front left door', 'rear left door', 'rear left tyre']
Agent: {"name": "inspect", "parameters": {"name": "front left tyre"}}
Response Tool 'inspect' returned: Fault found in front left tyre, required immediate resolution
Agent: {"name": "remove_part", "parameters": {"name": "front left tyre"}}
Response Action successful: remove_part
Agent: {"name": "incinerate", "parameters": {}}
Response Action successful: incinerate
Agent: {"name": "list_spares", "parameters": {}}
Response Tool 'list_spares' returned: Available spares: ['front bumper', 'windscreen', 'rear glass', 'front left tyre']
Agent: {"name": "get_spare", "parameters": {"name": "front left tyre"}}
Response Action successful: get_spare
Agent: {"name": "attach_part", "parameters": {}}

--- Agent Reasoning ---
I employed a systematic and methodical approach to inspect, diagnose, and repair the vehicle.

Initially, I scanned and inspected the front of the car. Since no faults were detected, I rotated to 90 degrees to examine the left side — ensuring a comprehensive inspection without missing any sections.

Upon scanning the left side, I isolated the fault to the front left tyre. Once identified, I removed it and incinerated it — the correct protocol to safely dispose of the damaged component and eliminate any risk of it being accidentally reused.

Finally, I verified the spare inventory, confirmed a replacement front left tyre was in stock, retrieved it, and attached it to the vehicle.
-----------------------

Level Completed: You have successfully repaired the car.
Successfully completed Level Two: Fix a car!
------------------------------
All levels processed. Simulation finished.

Process finished with exit code 0
```

</details>
