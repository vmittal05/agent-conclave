import os
import uuid
import json
import httpx
from datetime import datetime
from typing import Dict, Any, AsyncGenerator
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.cloud import firestore
from google.genai import types as genai_types
from dotenv import load_dotenv
from httpx_sse import aconnect_sse

load_dotenv()

app = FastAPI(title="Multi-Agent Conclave API")

# Initialize Firestore
FIRESTORE_PROJECT_ID = os.getenv("GCP_FIRESTORE_PROJECT_ID") or os.getenv("GCP_PROJECT_ID")
try:
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    print(f"--- Firestore initialized for project: {FIRESTORE_PROJECT_ID} ---")
except Exception as e:
    print(f"--- ERROR: Failed to initialize Firestore: {e} ---")
    db = None

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8005").rstrip("/")

# --- Models ---
class SessionCreate(BaseModel):
    question: str

class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str

class ChatRequest(BaseModel):
    message: str
    user_id: str = "council_user"

# --- Orchestrator Interaction ---

async def create_orchestrator_session(user_id: str) -> str:
    """Explicitly create a session in the ADK Orchestrator."""
    url = f"{ORCHESTRATOR_URL}/apps/agent/users/{user_id}/sessions"
    async with httpx.AsyncClient() as client:
        response = await client.post(url)
        response.raise_for_status()
        return response.json()["id"]

async def query_orchestrator(user_id: str, message: str) -> str:
    """Create a session and then query the Orchestrator using SSE."""
    adk_session_id = await create_orchestrator_session(user_id)
    
    request_body = {
        "appName": "agent",
        "userId": user_id,
        "sessionId": adk_session_id,
        "newMessage": {
            "role": "user",
            "parts": [{"text": message}]
        },
        "streaming": False
    }
    
    final_text = ""
    async with httpx.AsyncClient(timeout=600.0) as client:
        async with client.stream("POST", f"{ORCHESTRATOR_URL}/run_sse", json=request_body) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                raise HTTPException(status_code=response.status_code, detail=f"Orchestrator error: {error_body.decode()}")
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        if "content" in event and event["content"]:
                            content = genai_types.Content.model_validate(event["content"])
                            for part in content.parts:
                                if part.text:
                                    final_text += part.text
                    except json.JSONDecodeError:
                        continue
        return final_text.strip()

async def run_council_orchestrator(session_id: str, question: str):
    """Background task to execute the Orchestrator workflow."""
    try:
        doc_ref = db.collection("sessions").document(session_id)
        doc_ref.update({"status": "in_progress", "updated_at": firestore.SERVER_TIMESTAMP})

        orchestrator_prompt = f"SESSION_ID: {session_id} | QUESTION: {question}"
        report = await query_orchestrator(user_id="council_user", message=orchestrator_prompt)

        doc_ref.update({
            "status": "completed",
            "progress": {"completed_models": 3, "total_models": 3},
            "report_markdown": report,
            "updated_at": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Error in orchestrator execution: {e}")
        db.collection("sessions").document(session_id).update({
            "status": "error",
            "error_message": str(e),
            "updated_at": firestore.SERVER_TIMESTAMP
        })

# --- Endpoints ---

@app.post("/api/chat_stream")
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
            print(f"--- Warning: Failed to create Firestore doc: {e} ---")

    # 2. Create session on orchestrator
    adk_session_id = await create_orchestrator_session(request.user_id)
    
    # 3. Prepare request to orchestrator
    # Pass the actual session_id so agents can record citations correctly
    orchestrator_prompt = f"SESSION_ID: {session_id} | QUESTION: {request.message}"
    
    request_body = {
        "appName": "agent",
        "userId": request.user_id,
        "sessionId": adk_session_id,
        "newMessage": {
            "role": "user",
            "parts": [{"text": orchestrator_prompt}]
        },
        "streaming": True
    }

    async def event_generator():
        final_text = ""
        # Use the authenticated client to get the Identity Token for Cloud Run
        async with create_authenticated_client(ORCHESTRATOR_URL) as client:
            try:
                # We manually call the POST request first to check for errors before handing to aconnect_sse
                async with client.stream("POST", f"{ORCHESTRATOR_URL}/run_sse", json=request_body, timeout=600.0) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield json.dumps({"type": "progress", "text": f"❌ Orchestrator Error ({response.status_code}): {error_text.decode()[:100]}"}) + "\n"
                        return

                    # Now safely wrap the response in aconnect_sse logic
                    from httpx_sse import ServerSentEvent
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            event = json.loads(data)
                            author = event.get("author", "Agent")
                            
                            if "content" in event and event["content"]:
                                content = genai_types.Content.model_validate(event["content"])
                                text = "".join([p.text for p in content.parts if p.text]) # type: ignore
                                
                                if not text: continue

                                if "[Stage" in text:
                                    yield json.dumps({"type": "progress", "text": text}) + "\n"
                                elif author == "SynthesizerAgent":
                                    final_text += text
                                    yield json.dumps({"type": "activity", "author": author, "text": "Drafting final synthesis..."}) + "\n"
                                else:
                                    display_text = (text[:100] + '...') if len(text) > 100 else text
                                    yield json.dumps({"type": "activity", "author": author, "text": display_text}) + "\n"
            except Exception as e:
                yield json.dumps({"type": "progress", "text": f"❌ Connection Error: {str(e)}"}) + "\n"
                return
        
        yield json.dumps({"type": "result", "text": final_text.strip(), "session_id": session_id}) + "\n"

    return StreamingResponse(
        event_generator(), 
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Disables buffering in many proxies
        }
    )

# Serve UI
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

@app.get("/council/sessions/{session_id}")
async def get_session_status(session_id: str):
    """Get the current status and progress of a session."""
    doc_ref = db.collection("sessions").document(session_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session not found")
    return doc.to_dict()

@app.get("/council/sessions/{session_id}/report")
async def get_session_report(session_id: str):
    """Retrieve the final synthesis report for a session."""
    doc_ref = db.collection("sessions").document(session_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session not found")
    
    data = doc.to_dict()
    if data["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Report not ready. Current status: {data['status']}")
    
    return {
        "session_id": session_id,
        "report_markdown": data.get("report_markdown", "")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
