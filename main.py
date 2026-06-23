import levels
from config import Config
from levels import Level
import agent
import json
from openai import OpenAI
import os

def load_config():
    if not os.path.exists("config.json"):
        print("Error: config.json not found.")
        if input("Would you like to make one? (Y/n)").lower().strip() != "n":
            new_config = {
                "openai_conf": {
                    "base_url": input("Enter base url of your openai conf: ").strip(),
                    "api_key": input("Enter the api key: ").strip(),
                    "model": input("Enter the model to be used: ").strip()
                }
            }
            with open("config.json", "w") as f:
                json.dump(new_config, f, indent=2)
        else:
            return None
    with open("config.json", "r") as f:
        config_json = json.load(f)
    return Config.model_validate(config_json)

def main():
    config = load_config()
    if not config:
        return

    client = OpenAI(
        base_url=config.openai_conf.base_url,
        api_key=config.openai_conf.api_key,
    )

    level_files = ["level1.json", "level2.json"]

    for level_file in level_files:
        if not os.path.exists(level_file):
            print(f"Skipping {level_file}: File not found.")
            continue
            
        with open(level_file, "r") as f:
            levels_json = json.load(f)
        level = Level.model_validate(levels_json)

        success = agent.solve(client, config, level)
        if success:
            print(f"Successfully completed {level.name}!")
        else:
            print(f"Failed to complete {level.name}.")
        
        print("-" * 30)

    print("All levels processed. Simulation finished.")

if __name__ == "__main__":
    main()
