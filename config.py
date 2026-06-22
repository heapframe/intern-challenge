"""
This file loads the config and validates it with pydantic
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator


class OpenAIConf(BaseModel):
    base_url: str
    api_key: str
    model: str

    @field_validator("base_url")
    @classmethod
    def not_empty(cls, v: str):
        if not v.strip():
            raise ValueError("must not be empty")
        return v

class Config(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    openai_conf: OpenAIConf = Field(alias="openai_conf")

"""
with open("config.json", "r") as f:
    config_json = json.load(f)

config = Config.model_validate(config_json)

print(config.openai_conf.base_url)
print(config.openai_conf.api_key)
print(config.openai_conf.model)
"""