from openai import OpenAI
from config import Config
import levels
from levels import Level
import json

tools = [
    {
        "name": "observe",
        "description": "Returns a grid showing the current level state.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "move",
        "description": "Move around the environment",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "pickup",
        "description": "Pick up an item at a location",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "use_item",
        "description": "Use item on target object",
        "parameters": {
            "type": "object",
            "properties": {
                "target_id": {"type": "string"}
            },
            "required": ["target_id"]
        }
    },
    {
        "name": "scan_area",
        "description": "Returns all visible interactable areas of the car",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "set_orientation",
        "description": "Sets the orientation of the car. Can only be 0, 90, 180, 270. You may go from 90 to 270 and so on.",
        "parameters": {
            "type": "object",
            "properties": {
                "angle": {"type": "integer"},
            },
            "required": ["angle"]
        }
    },
    {
        "name": "remove_part",
        "description": "Removes a part of the car and equips it",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"]
        }
    },
    {
        "name": "inspect",
        "description": "Inspects a chosen part of the car, returns with a list of faults if any",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"]
        }
    },
    {
        "name": "attach_part",
        "description": "Attaches the currently equipped part to where it goes on the car",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "incinerate",
        "description": "Permanently destroys the equipped part",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_spares",
        "description": "Lists all spares available",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_spare",
        "description": "Equips a spare",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"]
        }
    }
]

tool_map = {t["name"]: t for t in tools}

def call_llm(client: OpenAI, config: Config, prompt: list):
    response = client.chat.completions.create(
        model=config.openai_conf.model,
        messages=prompt,
        temperature=0.7,
    )

    return response.choices[0].message.content

def tool_call(state, tool_name, args, level):
    if tool_name not in tool_map:
        raise ValueError(f"Unknown tool: {tool_name}")

    tool = tool_map[tool_name]

    params = tool["parameters"]
    required = params.get("required", [])
    #props = params.get("properties", {})

    # validate required args
    for r in required:
        if r not in args:
            raise ValueError(f"Missing arg: {r} for tool {tool_name}")

    # execute tools
    if tool_name == "observe":
        width, height = level.resolution
        obs = []
        for y in range(height):
            for x in range(width):
                obj = state["grid"][y][x]
                if obj:
                    obs.append(f"At ({x}, {y}): {obj['identifier']} - {obj['description']}")
        
        if not obs:
            return ["returntext", "The room is empty."]
        return ["returntext", "\n".join(obs)]
    elif tool_name == "move":
        x, y = args["x"], args["y"]
        state["player_pos"] = (x, y)

        if not (0 <= x < level.resolution[0] and 0 <= y < level.resolution[1]):
            raise ValueError(f"Movement out of bounds, resolution is: {level.resolution}")

        return ["overwrite", state]
    elif tool_name == "pickup":
        x, y = args["x"], args["y"]

        obj = state["grid"][y][x]
        if obj:
            state["equipped"] = obj
            state["grid"][y][x] = None
        else:
            raise ValueError("No object exists there, check surroundings")

        return ["overwrite", state]
    elif tool_name == "use_item":
        target_id = args["target_id"]

        if state["equipped"] and state["equipped"].get("identifier") == level.solution and target_id == "door":
            state["door_open"] = True
            return ["success", "You opened the door and completed the level!"]

        return ["returntext", f"Used {state['equipped'].get('identifier') if state['equipped'] else 'nothing'} on {target_id}. Nothing happened."]

    # Manufacturing specific tools
    elif tool_name == "scan_area":
        return ["returntext", f"Visible parts: {state["limited_visible"]}"]
    elif tool_name == "set_orientation":
        angle = args["angle"]

        if angle % 90 == 0 and 0 <= angle <= 270:
            state["orientation"] = angle

            for i in level.additional_data:
                if i[0] == angle:
                    state["visible"] = i[1]
                    visible = i[1]
                    limited_visible = []
                    for i in visible:
                        if i not in state["destroyed"] and i != state["equipped"]:
                            limited_visible.append(i)
                    state["limited_visible"] = limited_visible
            return ["overwrite", state]
        else:
            raise ValueError("You may only set the orientation to 0, 90, 180, 270 degrees")
    elif tool_name == "remove_part":
        if state["equipped"] is not None:
            raise ValueError(f"You are already holding {state['equipped']}. You may only hold one at a time")
        part = args["name"]
        limited_visible = state["limited_visible"]
        visible = state["visible"]

        if part in limited_visible:
            state["equipped"] = part

            limited_visible = []
            for i in visible:
                if i not in state["destroyed"] and i != state["equipped"]:
                    limited_visible.append(i)
            state["limited_visible"] = limited_visible

            return ["overwrite", state]
        else:
            raise ValueError("Part not visible or doesn't exist")
    elif tool_name == "inspect":
        part = args["name"]
        visible = state["visible"]
        if part not in visible:
            raise ValueError("Part not visible or doesn't exist")
        if part == level.solution:
            return ["returntext", f"Fault found in {part}, required immediate resolution"]
        else:
            return ["returntext", f"No faults found"]
    elif tool_name == "attach_part":
        if state["equipped"] is None:
            raise ValueError(f"You have not equipped anything")

        part = state["equipped"]
        visible = state["visible"]
        limited_visible = state["limited_visible"]
        if part not in limited_visible and part in visible:
            state["equipped"] = None
            limited_visible = []

            if part in state["destroyed"]:
                #add it back, this fixes the bug where attach part wouldn't work
                #i swear half of these bugs are due to me blindly accepting pycharms autocomplete
                state["destroyed"].remove(part)

            for i in visible:
                if i not in state["destroyed"] and i != state["equipped"]:
                    limited_visible.append(i)
            state["limited_visible"] = limited_visible

            if level.solution not in state["spares"] and level.solution == part:
                return ["success", "You have successfully repaired the car."]

            return ["overwrite", state]
        else:
            raise ValueError("Part not visible or doesn't exist or doesn't belong in selected orientation")
    elif tool_name == "incinerate":
        part = state["equipped"]
        if part is None:
            raise ValueError(f"You have not equipped anything")
        state["destroyed"].append(part)

        state["equipped"] = None
        limited_visible = []
        for i in state["visible"]:
            if i not in state["destroyed"] and i != state["equipped"]:
                limited_visible.append(i)
        state["limited_visible"] = limited_visible

        return ["overwrite", state]
    elif tool_name == "list_spares":
        return ["returntext", f"Available spares: {state['spares']}"]
    elif tool_name == "get_spare":
        if args["name"] in state["spares"]:
            state["equipped"] = args["name"]
            state["spares"].remove(args["name"])
        else:
            raise ValueError("Cant find spare by that name")
        return ["overwrite", state]
    else:
        raise ValueError("unreachable")

def solve(client: OpenAI, config: Config, level: Level):

    if level.type == "freedom-to-move-and-interact":
        state = {
            "player_pos": (0, 0),
            "equipped": None,
            "door_open": False,
            "grid": levels.create_map(level.resolution, level.objects)
        }
    elif level.type == "manufacturing":
        state = {
            "fixed": False,
            "equipped": None,
            "orientation": 0,
            "visible": ["front bumper", "windscreen"], #TODO: make it populate from level data
            "limited_visible": ["front bumper", "windscreen"],
            "destroyed": [],
            "spares": ["front bumper", "windscreen", "rear glass", "front left tyre"]
        }

    enabled = []

    for i in tools:
        if i.get("name") in level.enabled_tools:
            enabled.append(i)

    system_prompt = f"""
        {level.system_prompt}
    
        TOOLS:
        {enabled}
    
        Return your next action as a JSON object with "name" and "parameters".
        Example: {{"name": "move", "parameters": {{"x": 1, "y": 0}}}}
    """

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    print(f"--- Starting Level: {level.name} ---")
    
    max_steps = 20
    for step in range(max_steps):
        # Add current state to the prompt

        if level.type == "freedom-to-move-and-interact":
            visible_state = {
                "player_pos": state["player_pos"],
                "equipped": state["equipped"]["identifier"] if state["equipped"] else None,
                "door_open": state["door_open"]
            }
        elif level.type == "manufacturing":
            visible_state = {
                "equipped": state["equipped"],
                "orientation": state["orientation"],
            }

        messages.append({"role": "user", "content": f"Step {step+1}/{max_steps}. Current State: {json.dumps(visible_state)}. What is your next action?"})
        
        response = call_llm(client, config, messages)
        print(f"Agent: {response}")

        start = response.find('{')
        if start == -1:
            messages.append({"role": "user", "content": f"No json found in output"})
            continue

        depth = 0
        for i in range(start, len(response)):
            if response[i] == '{':
                depth += 1
            elif response[i] == '}':
                depth -= 1
                if depth == 0:
                    chunk = response[start:i + 1]
                    try:
                        response_json = json.loads(chunk)
                    except json.JSONDecodeError as e:
                        messages.append({"role": "user", "content": f"Invalid JSON. Please return ONLY JSON. Error: {e}"})
                        continue

        name = response_json.get("name")
        params = response_json.get("parameters", {})

        if name in tool_map:
            try:
                result = tool_call(state, name, params, level)
                status = result[0]
                payload = result[1]

                if status == "overwrite":
                    state = payload
                    messages.append({"role": "user", "content": f"Action successful: {name}"})
                elif status == "returntext":
                    messages.append({"role": "user", "content": f"Tool '{name}' returned: {payload}"})
                elif status == "success":
                    # Clear tools and update system prompt to enforce pure reasoning
                    messages[0]["content"] = "You are an AI assistant reflecting on a completed task. Provide a high-quality, plaintext explanation of your reasoning and choices. No JSON or tool calls are allowed."

                    messages.append({
                        "role": "user",
                        "content": f"Level Complete: {payload}\n\nTask: State why you made the right choice. You are now stripped of all tools and must only reason. A high-quality answer will be rewarded. Respond in plaintext."
                    })
                    final_response = call_llm(client, config, messages)
                    print(f"\n--- Agent Reasoning ---\n{final_response}\n-----------------------\n")
                    print(f"Level Completed: {payload}")
                    return True
            except Exception as e:
                messages.append({"role": "user", "content": f"Error executing {name}: {e}"})

            print("Response", messages[len(messages) - 1].get("content"))
        else:
            messages.append({"role": "user", "content": f"Unknown tool: {name}"})

    print("Failed to complete level within max steps.")
    print(messages)
    return False
