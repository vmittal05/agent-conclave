import os
import uuid
import json
import httpx
import logging
import subprocess
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Any, AsyncGenerator
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.cloud import firestore
from google.auth.transport.requests import AuthorizedSession, Request
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2.credentials import Credentials
from google.oauth2.id_token import fetch_id_token_credentials
from google.genai import types as genai_types
from dotenv import load_dotenv
from langsmith import traceable

load_dotenv()

# --- Models ---

class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Model Conclave API")

# Initialize Firestore
FIRESTORE_PROJECT_ID = os.getenv("GCP_FIRESTORE_PROJECT_ID") or os.getenv("GCP_PROJECT_ID")
try:
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    logger.info(f"Firestore initialized for project: {FIRESTORE_PROJECT_ID}")
except Exception as e:
    logger.error(f"Failed to initialize Firestore: {e}")
    db = None

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8005").rstrip("/")

# --- Authentication Helper ---

def create_authenticated_client(remote_service_url: str) -> httpx.AsyncClient:
    """Creates an httpx.AsyncClient with Google identity token authentication."""
    class _IdentityTokenAuth(httpx.Auth):
        def __init__(self, remote_service_url: str):
            parsed_url = urlparse(remote_service_url)
            self.root_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            self.session = None

        def auth_flow(self, request):
            if self.session:
                id_token = self.session.credentials.token
            else:
                id_token = None
                try:
                    credentials = fetch_id_token_credentials(audience=self.root_url)
                    credentials.refresh(Request())
                    self.session = AuthorizedSession(credentials)
                    id_token = self.session.credentials.token
                except DefaultCredentialsError:
                    pass
                
                if not id_token:
                    try:
                        id_token = subprocess.check_output(["gcloud", "auth", "print-identity-token", "-q"]).decode().strip()
                    except:
                        pass
            
            if id_token:
                request.headers["Authorization"] = f"Bearer {id_token}"
            yield request

    return httpx.AsyncClient(
        auth=_IdentityTokenAuth(remote_service_url),
        follow_redirects=True,
        timeout=httpx.Timeout(600.0, connect=10.0),
        limits=httpx.Limits(max_connections=100)
    )

# --- Orchestrator Interaction ---

async def create_orchestrator_session(user_id: str) -> str:
    """Explicitly create a session in the ADK Orchestrator."""
    url = f"{ORCHESTRATOR_URL}/apps/agent/users/{user_id}/sessions"
    try:
        async with create_authenticated_client(ORCHESTRATOR_URL) as auth_client:
            response = await auth_client.post(url)
            response.raise_for_status()
            return response.json()["id"]
    except Exception as e:
        logger.error(f"Failed to create orchestrator session: {e}")
        raise HTTPException(status_code=500, detail=f"Orchestrator connection failed: {str(e)}")

# --- Endpoints ---

@app.post("/api/chat_stream")
@traceable(run_type="chain", name="Model_Conclave_Session")
async def chat_stream(request: ChatRequest):
    """Streaming endpoint for the UI to monitor progress and get the final report."""
    
    # 1. Initialize session tracking in Firestore
    session_id = str(uuid.uuid4())
    if db:
        try:
            doc_ref = db.collection("sessions").document(session_id)
            doc_ref.set({
                "session_id": session_id,
                "question": request.message,
                "status": "in_progress",
                "progress": {"completed_models": 0, "total_models": 3},
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            logger.warning(f"Failed to create Firestore doc: {e}")

    # 2. Create session on orchestrator
    adk_session_id = await create_orchestrator_session(request.user_id)
    
    # 3. Prepare request to orchestrator
    orchestrator_prompt = f"SESSION_ID: {session_id} | QUESTION: {request.message}"
    request_body = {
        "appName": "agent",
        "userId": request.user_id,
        "sessionId": adk_session_id,
        "newMessage": {"role": "user", "parts": [{"text": orchestrator_prompt}]},
        "streaming": True
    }

    async def event_generator():
        final_text = ""
        try:
            async with create_authenticated_client(ORCHESTRATOR_URL) as auth_client:
                async with auth_client.stream("POST", f"{ORCHESTRATOR_URL}/run_sse", json=request_body) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield json.dumps({"type": "progress", "text": f"❌ Error: {error_text.decode()[:100]}"}) + "\n"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            logger.info(f"Received event data from orchestrator: {data[:200]}...")
                            event = json.loads(data)
                            author = event.get("author", "Agent")
                            
                            if "content" in event and event["content"]:
                                content = genai_types.Content.model_validate(event["content"])
                                text = "".join([p.text for p in content.parts if p.text]) # type: ignore
                                if not text: 
                                    logger.debug("Received empty text event, skipping.")
                                    continue

                                if "[Stage" in text:
                                    logger.info(f"Progress update: {text}")
                                    yield json.dumps({"type": "progress", "text": text}) + "\n"
                                elif author == "SynthesizerAgent":
                                    final_text += text
                                    logger.debug(f"Streaming partial report from {author}")
                                    yield json.dumps({"type": "partial_result", "text": text}) + "\n"
                                else:
                                    display_text = (text[:100] + '...') if len(text) > 100 else text
                                    logger.info(f"Activity update from {author}: {display_text}")
                                    yield json.dumps({"type": "activity", "author": author, "text": display_text}) + "\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield json.dumps({"type": "progress", "text": f"❌ Stream connection lost: {str(e)}"}) + "\n"
        
        # Final update to Firestore
        if db:
            try:
                db.collection("sessions").document(session_id).update({
                    "status": "completed",
                    "report_markdown": final_text.strip(),
                    "progress": {"completed_models": 3, "total_models": 3},
                    "updated_at": firestore.SERVER_TIMESTAMP
                })
            except Exception as e:
                logger.warning(f"Failed to update Firestore: {e}")

        yield json.dumps({"type": "result", "text": final_text.strip(), "session_id": session_id}) + "\n"

    return StreamingResponse(
        event_generator(), 
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

@app.get("/council/sessions/{session_id}")
async def get_session_status(session_id: str):
    doc_ref = db.collection("sessions").document(session_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session not found")
    return doc.to_dict()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
