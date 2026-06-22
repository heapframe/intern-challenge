# LLM Agent in a Virtual World

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
│  World State │ ─────────────── ▶ │     LLM     │ ─────────────────────▶ │ Tool Harness │
│  (dict)     │                   │             │                         │  (agent.py)  │
│             │ ◀─────────────── │             │ ◀───────────────────── │              │
└─────────────┘   state update    └─────────────┘    result / error       └──────────────┘
         ▲                                                                        │
         └────────────────────────── world mutation ──────────────────────────────┘
```

### Key Design Decisions

**Semantic state, not pixels.** The agent receives a structured JSON snapshot of what it can currently perceive — object names, positions, descriptions, and status flags. This forces the agent to reason about meaning rather than pattern-match on visual data.

**Per-level tool scoping.** Each level declares `enabled_tools`. The harness filters the global tool list before building the system prompt, so the LLM only sees actions that are valid in its current context. No special-casing needed in the dispatch logic.

**In-band error recovery.** Tool failures (wrong coordinate, nothing there, wrong orientation) are caught and returned as the next user message. The conversation history itself is the recovery mechanism — no external retry logic.

**Robust JSON extraction.** The response parser scans character-by-character for balanced `{}` using a brace-depth counter. The LLM can prepend natural-language reasoning to its response and the harness still reliably extracts the action.

**Post-completion reasoning elicitation.** On success, the system prompt is cleared of tool scaffolding and the agent is asked to explain its decision process in plain text. The full action history remains in context, so the explanation is grounded in what actually happened.

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
