from fastapi import FastAPI, HTTPException
from jose import jwt
from datetime import datetime, timedelta

app = FastAPI()

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"

VALID_USERS = {
    "hospital1": "password123",
    "hospital2": "password456"
}

@app.post("/login")
def login(hospital_id: str, password: str):
    if VALID_USERS.get(hospital_id) != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    payload = {
        "sub": hospital_id,
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token}

@app.post("/validate")
def validate(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"status": "valid", "hospital": payload["sub"]}
    except:
        raise HTTPException(status_code=401, detail="Invalid or expired token")