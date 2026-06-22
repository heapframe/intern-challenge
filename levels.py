from pydantic import BaseModel, Field, ConfigDict
from typing import List, Tuple
from pydantic import field_validator

class Position(BaseModel):
    x: int
    y: int

class Object(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    name: str
    position: Tuple[int, int]
    identifier: str
    description: str

class Level(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    system_prompt: str
    solution: str
    resolution: Tuple[int, int]
    objects: List[Object]
    enabled_tools: List[str]
    type: str
    additional_data: List[List]

    @field_validator("objects")
    @classmethod
    def check_positions(cls, objects, info):
        res_x, res_y = info.data["resolution"]

        for obj in objects:
            x, y = obj.position
            if not (0 <= x < res_x and 0 <= y < res_y):
                raise ValueError(f"Object out of bounds: {obj.identifier}")

        return objects

def create_map(resolution: Tuple[int, int], objects: List[object]):
    width, height = resolution

    # 2D grid init
    grid = [
        [None for _ in range(width)]
        for _ in range(height)
    ]

    # place objects
    for obj in objects:
        x, y = obj.position

        # bounds safety
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = {
                "type": obj.type,
                "name": obj.name,
                "identifier": obj.identifier,
                "description": obj.description
            }

    return grid