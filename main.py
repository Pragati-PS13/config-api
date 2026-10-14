
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}


def coerce(key, value):
    value = str(value)

    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        return value.strip().lower() in ("true", "1", "yes", "on")

    return value


def normalize_key(key):
    key = key.strip()

    if key.upper() == "NUM_WORKERS":
        return "workers"

    if key.upper().startswith("APP_"):
        key = key[4:]

    return key.lower()


def apply_layer(config, values):
    for raw_key, value in values.items():
        if value is None:
            continue

        key = normalize_key(raw_key)
        config[key] = coerce(key, value)


@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    environment = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"

    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as file:
            yaml_values = yaml.safe_load(file) or {}
        apply_layer(config, yaml_values)

    # Layer 3: .env file
    env_file = dotenv_values(BASE_DIR / ".env")
    apply_layer(config, env_file)

    # Layer 4: OS environment variables with APP_ prefix
    os_values = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_") and key != "APP_ENV"
    }
    apply_layer(config, os_values)

    # Layer 5: CLI-style query overrides
    for item in set:
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        key = normalize_key(key)
        config[key] = coerce(key, value)

    # Never expose the actual API key
    config["api_key"] = "****"

    return config
