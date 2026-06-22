from openai import OpenAI
from config import Config
import json

with open("config.json", "r") as f:
    config_json = json.load(f)

config = Config.model_validate(config_json)

client = OpenAI(
    base_url=config.openai_conf.base_url,
    api_key=config.openai_conf.api_key,
)

response = client.chat.completions.create(
    model=config.openai_conf.model,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ],
    temperature=0.7,
)

print(response.choices[0].message.content)