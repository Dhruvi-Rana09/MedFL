import os

MIN_UPDATES_TO_AGGREGATE = 2

# Parse comma-separated hospital URLs from environment
_raw = os.getenv("HOSPITAL_URLS", "")
HOSPITAL_URLS = [url.strip() for url in _raw.split(",") if url.strip()]

MODEL_STORAGE_URL = "http://model-storage:8000"