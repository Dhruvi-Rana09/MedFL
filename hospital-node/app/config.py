import os

AGGREGATOR_URL = "http://aggregator:8000"
HOSPITAL_ID = os.getenv("HOSPITAL_ID", "hospital-1")  # fallback default
INPUT_SIZE = 10