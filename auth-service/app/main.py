from fastapi import FastAPI, HTTPException

app = FastAPI()

VALID_TOKENS = ["hospital_secret"]

@app.post("/validate")
def validate(token: str):
    if token not in VALID_TOKENS:
        raise HTTPException(status_code=403, detail="Invalid token")
    return {"status": "valid"}