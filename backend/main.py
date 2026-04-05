import os
import uuid
import json
import httpx
from datetime import datetime
from typing import Dict, Any, AsyncGenerator
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from google.cloud import firestore
from google.genai import types as genai_types
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Multi-Agent Conclave API")

# Initialize Firestore
db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8005").rstrip("/")

# --- Models ---
class SessionCreate(BaseModel):
    question: str

class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str

# --- Orchestrator Interaction ---

async def create_orchestrator_session(user_id: str) -> str:
    """Explicitly create a session in the ADK Orchestrator."""
    # The default app name is "agent" when run from the root of the service
    url = f"{ORCHESTRATOR_URL}/apps/agent/users/{user_id}/sessions"
    async with httpx.AsyncClient() as client:
        response = await client.post(url)
        response.raise_for_status()
        return response.json()["id"]

async def query_orchestrator(user_id: str, message: str) -> str:
    """Create a session and then query the Orchestrator using SSE."""
    # 1. Create the session first (fixes 404 Session Not Found)
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
        # Update Firestore to 'in_progress'
        doc_ref = db.collection("sessions").document(session_id)
        doc_ref.update({"status": "in_progress", "updated_at": firestore.SERVER_TIMESTAMP})

        # Run Orchestrator
        # We include the session_id in the prompt so the Synthesizer knows which citations to query
        orchestrator_prompt = f"Session ID: {session_id}. Question: {question}"
        report = await query_orchestrator(user_id="council_user", message=orchestrator_prompt)

        # Final Update to Firestore
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

from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from httpx_sse import aconnect_sse

# --- Models ---
class ChatRequest(BaseModel):
    message: str
    user_id: str = "council_user"

# --- Endpoints ---

@app.post("/api/chat_stream")
async def chat_stream(request: ChatRequest):
    """Streaming endpoint for the UI to monitor progress and get the final report."""
    
    # 1. Create session on orchestrator
    adk_session_id = await create_orchestrator_session(request.user_id)
    
    # 2. Prepare request to orchestrator
    request_body = {
        "appName": "agent",
        "userId": request.user_id,
        "sessionId": adk_session_id,
        "newMessage": {
            "role": "user",
            "parts": [{"text": request.message}]
        },
        "streaming": False
    }

    async def event_generator():
        final_text = ""
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with aconnect_sse(client, "POST", f"{ORCHESTRATOR_URL}/run_sse", json=request_body) as event_source:
                async for server_event in event_source.aiter_sse():
                    event = server_event.json()
                    author = event.get("author", "Agent")
                    
                    if "content" in event and event["content"]:
                        content = genai_types.Content.model_validate(event["content"])
                        text = "".join([p.text for p in content.parts if p.text]) # type: ignore
                        
                        if not text: continue

                        if "[Stage" in text:
                            # Explicit stage progress
                            yield json.dumps({"type": "progress", "text": text}) + "\n"
                        elif author == "SynthesizerAgent":
                            # Final report accumulation
                            final_text += text
                            # Also show activity for synthesizer
                            yield json.dumps({"type": "activity", "author": author, "text": "Drafting final synthesis..."}) + "\n"
                        else:
                            # Pass through research agent activity (thoughts/tool updates)
                            # Truncate long thoughts for the activity log
                            display_text = (text[:100] + '...') if len(text) > 100 else text
                            yield json.dumps({"type": "activity", "author": author, "text": display_text}) + "\n"
        
        # Send final result
        yield json.dumps({"type": "result", "text": final_text.strip()}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

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
