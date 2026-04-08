from fastapi import FastAPI, HTTPException
from app.storage import save_model, load_model, list_versions

app = FastAPI()


@app.get("/")
def health():
    return {"status": "Model Storage Service Running"}


@app.post("/store")
def store(model: dict):
    version = save_model(model)

    return {
        "message": "Model stored successfully",
        "version": version
    }


@app.get("/load")
def load(version: int = None):
    data = load_model(version)

    if data is None:
        raise HTTPException(status_code=404, detail="Model not found")

    return data


@app.get("/versions")
def versions():
    return {"available_versions": list_versions()}