import os
import json
from datetime import datetime

# Directory where models will be stored
MODEL_DIR = "app/models"

# Ensure directory exists
os.makedirs(MODEL_DIR, exist_ok=True)


def get_next_version():
    files = os.listdir(MODEL_DIR)

    if not files:
        return 1

    versions = []
    for f in files:
        try:
            v = int(f.split("_v")[1].split(".")[0])
            versions.append(v)
        except:
            continue

    return max(versions) + 1


def save_model(model_data: dict):
    version = get_next_version()
    file_path = f"{MODEL_DIR}/model_v{version}.json"

    payload = {
        "version": version,
        "timestamp": str(datetime.utcnow()),
        "model": model_data
    }

    with open(file_path, "w") as f:
        json.dump(payload, f)

    return version


def load_model(version: int = None):
    files = os.listdir(MODEL_DIR)

    if not files:
        return None

    versions = []
    for f in files:
        try:
            v = int(f.split("_v")[1].split(".")[0])
            versions.append(v)
        except:
            continue

    if version is None:
        version = max(versions)

    file_path = f"{MODEL_DIR}/model_v{version}.json"

    if not os.path.exists(file_path):
        return None

    with open(file_path, "r") as f:
        return json.load(f)


def list_versions():
    files = os.listdir(MODEL_DIR)

    versions = []
    for f in files:
        try:
            v = int(f.split("_v")[1].split(".")[0])
            versions.append(v)
        except:
            continue

    return sorted(versions)
