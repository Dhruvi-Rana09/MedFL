from fastapi import FastAPI
import requests

app = FastAPI()

global_model = {"weights": [0.5, 0.5]}

updates = []

@app.get("/")
def root():
    return {"message": "Aggregator Running"}

@app.post("/receive-update")
def receive_update(update: dict):
    updates.append(update["weights"])
    return {"status": "received"}

@app.get("/aggregate")
def aggregate():
    global global_model
    if not updates:
        return {"message": "No updates"}

    avg = [sum(x)/len(x) for x in zip(*updates)]
    global_model["weights"] = avg
    updates.clear()

    return {"global_model": global_model}

@app.get("/send-model")
def send_model():
    return global_model