from fastapi import FastAPI

app = FastAPI()

logs = []

@app.post("/log")
def log(data: dict):
    logs.append(data)
    return {"status": "logged"}

@app.get("/logs")
def get_logs():
    return logs