from fastapi import FastAPI
import requests
import random

app = FastAPI()

AGGREGATOR_URL = "http://aggregator:8000"

@app.get("/")
def root():
    return {"message": "Hospital Node Running"}

@app.get("/train")
def train():
    # Fake training (simulate ML)
    weights = [random.random(), random.random()]

    requests.post(f"{AGGREGATOR_URL}/receive-update",
                  json={"weights": weights})

    return {"trained_weights": weights}