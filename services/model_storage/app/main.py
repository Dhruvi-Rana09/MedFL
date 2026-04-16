import os
import io
import json
import logging
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from pydantic import BaseModel
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

app = FastAPI(title="MedFL Model Storage Service")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "medfl-models")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"

def _get_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )

def ensure_bucket():
    client = _get_client()
    try:
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
    except Exception as e:
        logger.error(f"Error ensuring bucket: {e}")

@app.on_event("startup")
def on_startup():
    ensure_bucket()

class MetadataPayload(BaseModel):
    metadata_json: str

@app.post("/models/upload")
async def upload_model(
    round_id: int = Form(...),
    model_file: UploadFile = File(...),
    metadata_json: str = Form(...)
):
    ensure_bucket()
    client = _get_client()
    
    try:
        model_bytes = await model_file.read()
        
        # Upload model
        client.put_object(
            MINIO_BUCKET, 
            f"round_{round_id}/model.pt", 
            io.BytesIO(model_bytes), 
            len(model_bytes), 
            content_type="application/octet-stream"
        )
        
        # Upload metadata
        meta_bytes = metadata_json.encode('utf-8')
        client.put_object(
            MINIO_BUCKET, 
            f"round_{round_id}/metadata.json", 
            io.BytesIO(meta_bytes), 
            len(meta_bytes), 
            content_type="application/json"
        )
        
        # Upload pointer
        pointer_bytes = str(round_id).encode('utf-8')
        client.put_object(
            MINIO_BUCKET,
            "latest_round",
            io.BytesIO(pointer_bytes),
            len(pointer_bytes),
            content_type="text/plain"
        )
        
        return {"status": "ok", "round": round_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models/latest")
async def get_latest_model():
    client = _get_client()
    try:
        response = client.get_object(MINIO_BUCKET, "latest_round")
        pointer_bytes = response.read()
        response.close()
        response.release_conn()
        
        round_id = int(pointer_bytes.decode('utf-8').strip())
        
        response = client.get_object(MINIO_BUCKET, f"round_{round_id}/model.pt")
        model_bytes = response.read()
        response.close()
        response.release_conn()
        
        return Response(content=model_bytes, media_type="application/octet-stream")
    except S3Error as e:
        if e.code == "NoSuchKey":
            return Response(content=b"", status_code=204) # No model yet
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
