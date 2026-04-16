import io
import os
import json
import torch
from typing import Optional, List
from minio import Minio
from minio.error import S3Error

BUCKET = "medfl-models"

def _get_client() -> Minio:
    return Minio(
        os.environ["MINIO_ENDPOINT"],       # e.g. "minio:9000"
        access_key=os.environ["MINIO_USER"],
        secret_key=os.environ["MINIO_PASS"],
        secure=False,
    )

def ensure_bucket() -> None:
    try:
        client = _get_client()
        if not client.bucket_exists(BUCKET):
            client.make_bucket(BUCKET)
    except Exception as e:
        print(f"[Registry] Warning: Could not ensure bucket exists: {e}")

def save_model(round_id: int, state_dict: dict, metadata: dict) -> None:
    try:
        ensure_bucket()
        client = _get_client()
        
        # Serialize model
        model_buf = io.BytesIO()
        torch.save(state_dict, model_buf)
        model_bytes = model_buf.getvalue()
        
        # Upload model
        client.put_object(
            BUCKET, 
            f"round_{round_id}/model.pt", 
            io.BytesIO(model_bytes), 
            len(model_bytes), 
            content_type="application/octet-stream"
        )
        
        # Serialize metadata
        meta_bytes = json.dumps(metadata).encode('utf-8')
        
        # Upload metadata
        client.put_object(
            BUCKET, 
            f"round_{round_id}/metadata.json", 
            io.BytesIO(meta_bytes), 
            len(meta_bytes), 
            content_type="application/json"
        )
        
        # Upload pointer
        pointer_bytes = str(round_id).encode('utf-8')
        client.put_object(
            BUCKET,
            "latest_round",
            io.BytesIO(pointer_bytes),
            len(pointer_bytes),
            content_type="text/plain"
        )
        
        print(f"[Registry] Checkpoint saved: round_{round_id}")
    except Exception as e:
        print(f"[Registry] Error saving model: {e}")

def load_latest_model() -> Optional[dict]:
    try:
        client = _get_client()
        
        # Try to get object "latest_round"
        response = client.get_object(BUCKET, "latest_round")
        pointer_bytes = response.read()
        response.close()
        response.release_conn()
        
        round_id = int(pointer_bytes.decode('utf-8').strip())
        
        # Get object f"round_{round_id}/model.pt"
        response = client.get_object(BUCKET, f"round_{round_id}/model.pt")
        model_bytes = response.read()
        response.close()
        response.release_conn()
        
        # torch.load from BytesIO
        try:
            state_dict = torch.load(io.BytesIO(model_bytes), weights_only=True)
        except TypeError:
            state_dict = torch.load(io.BytesIO(model_bytes))
            
        print(f"[Registry] Loaded checkpoint from round {round_id}")
        return state_dict
    except S3Error as e:
        print(f"[Registry] S3 Warning on load_latest_model: {e}")
        return None
    except Exception as e:
        print(f"[Registry] Warning on load_latest_model: {e}")
        return None

def load_round_metadata(round_id: int) -> Optional[dict]:
    try:
        client = _get_client()
        response = client.get_object(BUCKET, f"round_{round_id}/metadata.json")
        meta_bytes = response.read()
        response.close()
        response.release_conn()
        return json.loads(meta_bytes.decode('utf-8'))
    except Exception as e:
        print(f"[Registry] Warning on load_round_metadata: {e}")
        return None

def list_rounds() -> List[int]:
    try:
        client = _get_client()
        objects = client.list_objects(BUCKET, prefix="", recursive=True)
        
        rounds = []
        for obj in objects:
            name = obj.object_name
            if name.startswith("round_") and name.endswith("/model.pt"):
                parts = name.split("/")
                if len(parts) == 2:
                    try:
                        r_id = int(parts[0].replace("round_", ""))
                        rounds.append(r_id)
                    except ValueError:
                        pass
        return sorted(rounds)
    except Exception as e:
        print(f"[Registry] Warning on list_rounds: {e}")
        return []
