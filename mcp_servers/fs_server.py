import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="File System (GCS) MCP Server")

# --- Configuration ---
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")

# --- Client Initialization ---
storage_client = None

def get_storage_client():
    global storage_client
    if storage_client is None:
        storage_client = storage.Client(project=GCP_PROJECT_ID)
    return storage_client

class GCSWriteRequest(BaseModel):
    file_path: str
    content: str
    content_type: Optional[str] = "text/plain"

class GCSReadRequest(BaseModel):
    file_path: str

@app.post("/tools/gcs_write")
async def gcs_write(req: GCSWriteRequest):
    """Write a file to GCS. Supports text or base64 binary content."""
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME not configured")
        
    logger.info(f"Writing to GCS: {req.file_path} (Type: {req.content_type})")
    client = get_storage_client()
    try:
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(req.file_path)
        
        # Determine content to upload
        is_binary = False
        if req.content_type in ["image/png", "image/jpeg"] or len(req.content) > 1000:
            try:
                # Attempt to decode as base64
                data_to_upload = base64.b64decode(req.content)
                is_binary = True
            except:
                data_to_upload = req.content
        else:
            data_to_upload = req.content

        # Upload with content type
        if is_binary:
            blob.upload_from_string(data_to_upload, content_type=req.content_type)
        else:
            blob.upload_from_string(data_to_upload, content_type=req.content_type)
        
        # Ensure the blob is publicly readable
        try:
            blob.make_public()
        except Exception as e:
            logger.warning(f"Could not make blob public (might be bucket policy): {e}")
            
        import time
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{req.file_path}?t={int(time.time())}"
        logger.info(f"Successfully uploaded to GCS. Public URL: {public_url}")
            
        return {
            "status": "success",
            "gs_path": f"gs://{GCS_BUCKET_NAME}/{req.file_path}",
            "public_url": public_url
        }
    except Exception as e:
        logger.error(f"GCS Write Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/gcs_read")
async def gcs_read(req: GCSReadRequest):
    """Read a file from GCS."""
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME not configured")
        
    logger.info(f"Reading from GCS: {req.file_path}")
    client = get_storage_client()
    try:
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(req.file_path)
        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found")
            
        content = blob.download_as_text()
        return {"content": content}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"GCS Read Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tools/gcs_list")
async def gcs_list(prefix: Optional[str] = None):
    """List files in the GCS bucket."""
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME not configured")
        
    logger.info(f"Listing GCS bucket: {GCS_BUCKET_NAME} with prefix: {prefix}")
    client = get_storage_client()
    try:
        blobs = client.list_blobs(GCS_BUCKET_NAME, prefix=prefix)
        file_list = [blob.name for blob in blobs]
        return {"files": file_list}
    except Exception as e:
        logger.error(f"GCS List Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Default port for FS MCP is 8014
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8014)))
