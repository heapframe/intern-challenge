"""
Tests for the LLM agent harness.
Run with: python -m pytest tests.py -v
"""
import json
import pytest
from pydantic import ValidationError

from levels import Object, Level, create_map
from agent import tool_call, tools, tool_map


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_level1():
    with open("level1.json") as f:
        return Level.model_validate(json.load(f))

def make_level2():
    with open("level2.json") as f:
        return Level.model_validate(json.load(f))

def make_grid_state(level):
    """Fresh state for a freedom-to-move-and-interact level."""
    import levels as lvl_module
    return {
        "player_pos": (0, 0),
        "equipped": None,
        "door_open": False,
        "grid": lvl_module.create_map(level.resolution, level.objects),
    }

def make_manufacturing_state():
    """Fresh state for a manufacturing level."""
    return {
        "fixed": False,
        "equipped": None,
        "orientation": 0,
        "visible": ["front bumper", "windscreen"],
        "limited_visible": ["front bumper", "windscreen"],
        "destroyed": [],
        "spares": ["front bumper", "windscreen", "rear glass", "front left tyre"],
    }


# ---------------------------------------------------------------------------
# levels.py — create_map
# ---------------------------------------------------------------------------

class TestCreateMap:
    def test_empty_objects(self):
        grid = create_map((3, 3), [])
        assert grid == [[None, None, None], [None, None, None], [None, None, None]]

    def test_object_placed_at_correct_position(self):
        level = make_level1()
        grid = create_map(level.resolution, level.objects)
        # red key is at (1, 0) → grid[row=0][col=1]
        cell = grid[0][1]
        assert cell is not None
        assert cell["identifier"] == "red key"

    def test_grid_dimensions_match_resolution(self):
        level = make_level1()
        grid = create_map(level.resolution, level.objects)
        width, height = level.resolution
        assert len(grid) == height
        assert all(len(row) == width for row in grid)

    def test_empty_cells_are_none(self):
        level = make_level1()
        grid = create_map(level.resolution, level.objects)
        # (0, 0) has no object
        assert grid[0][0] is None


# ---------------------------------------------------------------------------
# levels.py — Pydantic validation
# ---------------------------------------------------------------------------

class TestLevelValidation:
    def test_valid_level1_loads(self):
        level = make_level1()
        assert level.name == "Level One: Door puzzle"
        assert level.solution == "blue key"

    def test_valid_level2_loads(self):
        level = make_level2()
        assert level.name == "Level Two: Fix a car"
        assert level.solution == "front left tyre"

    def test_object_out_of_bounds_raises(self):
        with pytest.raises(ValidationError):
            Level.model_validate({
                "name": "bad",
                "system_prompt": "x",
                "solution": "x",
                "resolution": [3, 3],
                "enabled_tools": [],
                "type": "freedom-to-move-and-interact",
                "additional_data": [],
                "objects": [{
                    "type": "item",
                    "name": "thing",
                    "position": [99, 99],   # out of bounds
                    "identifier": "thing",
                    "description": "oob",
                }]
            })

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            Level.model_validate({
                "name": "x", "system_prompt": "x", "solution": "x",
                "resolution": [3, 3], "enabled_tools": [], "type": "x",
                "additional_data": [], "objects": [],
                "unexpected_field": True,
            })


# ---------------------------------------------------------------------------
# agent.py — tool registry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_all_tools_have_required_keys(self):
        for t in tools:
            assert "name" in t
            assert "description" in t
            assert "parameters" in t

    def test_tool_map_matches_tools_list(self):
        assert set(tool_map.keys()) == {t["name"] for t in tools}

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            tool_call({}, "nonexistent_tool", {}, make_level1())

    def test_missing_required_arg_raises(self):
        level = make_level1()
        state = make_grid_state(level)
        with pytest.raises(ValueError, match="Missing arg"):
            tool_call(state, "move", {}, level)   # move requires x and y


# ---------------------------------------------------------------------------
# agent.py — grid world tools (Level 1)
# ---------------------------------------------------------------------------

class TestObserve:
    def test_observe_returns_all_objects(self):
        level = make_level1()
        state = make_grid_state(level)
        status, text = tool_call(state, "observe", {}, level)
        assert status == "returntext"
        assert "red key" in text
        assert "green key" in text
        assert "blue key" in text
        assert "door" in text

    def test_observe_empty_grid(self):
        level = make_level1()
        state = make_grid_state(level)
        # clear the grid
        state["grid"] = [[None] * 6 for _ in range(6)]
        status, text = tool_call(state, "observe", {}, level)
        assert status == "returntext"
        assert text == "The room is empty."


class TestMove:
    def test_move_updates_player_pos(self):
        level = make_level1()
        state = make_grid_state(level)
        status, new_state = tool_call(state, "move", {"x": 2, "y": 3}, level)
        assert status == "overwrite"
        assert new_state["player_pos"] == (2, 3)

    def test_move_out_of_bounds_raises(self):
        level = make_level1()
        state = make_grid_state(level)
        with pytest.raises(ValueError, match="out of bounds"):
            tool_call(state, "move", {"x": 99, "y": 99}, level)


class TestPickup:
    def test_pickup_equips_object_and_clears_cell(self):
        level = make_level1()
        state = make_grid_state(level)
        # blue key is at (5, 0)
        status, new_state = tool_call(state, "pickup", {"x": 5, "y": 0}, level)
        assert status == "overwrite"
        assert new_state["equipped"]["identifier"] == "blue key"
        assert new_state["grid"][0][5] is None

    def test_pickup_empty_cell_raises(self):
        level = make_level1()
        state = make_grid_state(level)
        with pytest.raises(ValueError, match="No object exists"):
            tool_call(state, "pickup", {"x": 0, "y": 0}, level)


class TestUseItem:
    def _state_with_blue_key(self, level):
        state = make_grid_state(level)
        state["equipped"] = {"identifier": "blue key", "name": "key", "type": "item"}
        state["grid"][0][5] = None
        return state

    def test_correct_key_opens_door(self):
        level = make_level1()
        state = self._state_with_blue_key(level)
        status, msg = tool_call(state, "use_item", {"target_id": "door"}, level)
        assert status == "success"
        assert "opened the door" in msg

    def test_wrong_key_does_nothing(self):
        level = make_level1()
        state = make_grid_state(level)
        state["equipped"] = {"identifier": "red key", "name": "key", "type": "item"}
        status, msg = tool_call(state, "use_item", {"target_id": "door"}, level)
        assert status == "returntext"
        assert "Nothing happened" in msg

    def test_no_item_equipped_does_nothing(self):
        level = make_level1()
        state = make_grid_state(level)
        status, msg = tool_call(state, "use_item", {"target_id": "door"}, level)
        assert status == "returntext"
        assert "Nothing happened" in msg


# ---------------------------------------------------------------------------
# agent.py — manufacturing tools (Level 2)
# ---------------------------------------------------------------------------

class TestScanArea:
    def test_returns_limited_visible(self):
        level = make_level2()
        state = make_manufacturing_state()
        status, text = tool_call(state, "scan_area", {}, level)
        assert status == "returntext"
        assert "front bumper" in text
        assert "windscreen" in text


class TestSetOrientation:
    def test_valid_orientation_updates_state(self):
        level = make_level2()
        state = make_manufacturing_state()
        status, new_state = tool_call(state, "set_orientation", {"angle": 90}, level)
        assert status == "overwrite"
        assert new_state["orientation"] == 90
        assert "front left tyre" in new_state["limited_visible"]

    def test_invalid_orientation_raises(self):
        level = make_level2()
        state = make_manufacturing_state()
        with pytest.raises(ValueError, match="0, 90, 180, 270"):
            tool_call(state, "set_orientation", {"angle": 45}, level)

    def test_all_valid_orientations_accepted(self):
        level = make_level2()
        for angle in [0, 90, 180, 270]:
            state = make_manufacturing_state()
            status, _ = tool_call(state, "set_orientation", {"angle": angle}, level)
            assert status == "overwrite"


class TestInspect:
    def _rotated_state(self):
        """State rotated to 90° so front left tyre is visible."""
        level = make_level2()
        state = make_manufacturing_state()
        tool_call(state, "set_orientation", {"angle": 90}, level)
        return level, state

    def test_faulty_part_returns_fault(self):
        level, state = self._rotated_state()
        status, text = tool_call(state, "inspect", {"name": "front left tyre"}, level)
        assert status == "returntext"
        assert "Fault found" in text

    def test_healthy_part_returns_no_fault(self):
        level, state = self._rotated_state()
        status, text = tool_call(state, "inspect", {"name": "front left door"}, level)
        assert status == "returntext"
        assert "No faults found" in text

    def test_invisible_part_raises(self):
        level = make_level2()
        state = make_manufacturing_state()   # orientation 0 — only front/windscreen visible
        with pytest.raises(ValueError, match="not visible"):
            tool_call(state, "inspect", {"name": "front left tyre"}, level)


class TestRemovePart:
    def _state_at_90(self):
        level = make_level2()
        state = make_manufacturing_state()
        tool_call(state, "set_orientation", {"angle": 90}, level)
        return level, state

    def test_remove_visible_part(self):
        level, state = self._state_at_90()
        status, new_state = tool_call(state, "remove_part", {"name": "front left tyre"}, level)
        assert status == "overwrite"
        assert new_state["equipped"] == "front left tyre"
        assert "front left tyre" not in new_state["limited_visible"]

    def test_remove_invisible_part_raises(self):
        level = make_level2()
        state = make_manufacturing_state()   # orientation 0
        with pytest.raises(ValueError, match="not visible"):
            tool_call(state, "remove_part", {"name": "front left tyre"}, level)

    def test_remove_when_already_holding_raises(self):
        level, state = self._state_at_90()
        state["equipped"] = "something"
        with pytest.raises(ValueError, match="already holding"):
            tool_call(state, "remove_part", {"name": "front left tyre"}, level)


class TestIncinerate:
    def test_incinerate_destroys_equipped(self):
        level = make_level2()
        state = make_manufacturing_state()
        state["equipped"] = "front left tyre"
        status, new_state = tool_call(state, "incinerate", {}, level)
        assert status == "overwrite"
        assert new_state["equipped"] is None
        assert "front left tyre" in new_state["destroyed"]

    def test_incinerate_nothing_raises(self):
        level = make_level2()
        state = make_manufacturing_state()
        with pytest.raises(ValueError, match="not equipped"):
            tool_call(state, "incinerate", {}, level)


class TestListSpares:
    def test_lists_all_spares(self):
        level = make_level2()
        state = make_manufacturing_state()
        status, text = tool_call(state, "list_spares", {}, level)
        assert status == "returntext"
        assert "front left tyre" in text


class TestGetSpare:
    def test_get_spare_equips_and_removes_from_inventory(self):
        level = make_level2()
        state = make_manufacturing_state()
        status, new_state = tool_call(state, "get_spare", {"name": "front left tyre"}, level)
        assert status == "overwrite"
        assert new_state["equipped"] == "front left tyre"
        assert "front left tyre" not in new_state["spares"]

    def test_get_nonexistent_spare_raises(self):
        level = make_level2()
        state = make_manufacturing_state()
        with pytest.raises(ValueError, match="Cant find spare"):
            tool_call(state, "get_spare", {"name": "flux capacitor"}, level)


class TestAttachPart:
    def _state_ready_to_attach(self):
        """Rotate to 90°, remove faulty tyre, incinerate it, get the spare."""
        level = make_level2()
        state = make_manufacturing_state()
        tool_call(state, "set_orientation", {"angle": 90}, level)
        tool_call(state, "remove_part", {"name": "front left tyre"}, level)
        tool_call(state, "incinerate", {}, level)
        tool_call(state, "get_spare", {"name": "front left tyre"}, level)
        return level, state

    def test_attach_solution_part_returns_success(self):
        level, state = self._state_ready_to_attach()
        status, msg = tool_call(state, "attach_part", {}, level)
        assert status == "success"
        assert "successfully repaired" in msg

    def test_attach_nothing_raises(self):
        level = make_level2()
        state = make_manufacturing_state()
        with pytest.raises(ValueError, match="not equipped"):
            tool_call(state, "attach_part", {}, level)


# ---------------------------------------------------------------------------
# agent.py — JSON extraction logic (inline, no LLM needed)
# ---------------------------------------------------------------------------

class TestJsonExtraction:
    """Re-implements the brace-depth extractor from agent.py to verify it
    handles the edge cases the harness was designed for."""

    @staticmethod
    def extract(response: str):
        start = response.find('{')
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(response)):
            if response[i] == '{':
                depth += 1
            elif response[i] == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(response[start:i + 1])
        return None

    def test_clean_json(self):
        result = self.extract('{"name": "move", "parameters": {"x": 1, "y": 0}}')
        assert result == {"name": "move", "parameters": {"x": 1, "y": 0}}

    def test_json_with_leading_prose(self):
        result = self.extract('I will now move. {"name": "move", "parameters": {"x": 1, "y": 0}}')
        assert result["name"] == "move"

    def test_json_with_trailing_prose(self):
        result = self.extract('{"name": "observe", "parameters": {}} This should observe the area.')
        assert result["name"] == "observe"

    def test_no_json_returns_none(self):
        assert self.extract("I cannot determine the next action.") is None

    def test_nested_json_extracted_correctly(self):
        result = self.extract('{"name": "move", "parameters": {"x": 3, "y": 5}}')
        assert result["parameters"]["x"] == 3
        assert result["parameters"]["y"] == 5
