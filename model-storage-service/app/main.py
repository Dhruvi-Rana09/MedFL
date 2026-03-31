from fastapi import FastAPI

app = FastAPI()
stored_model = {}

@app.post("/store")
def store(model: dict):
    global stored_model
    stored_model = model
    return {"status": "stored"}

@app.get("/load")
def load():
    return stored_model