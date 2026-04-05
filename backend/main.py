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

async def query_orchestrator(user_id: str, session_id: str, message: str) -> str:
    """Query the Orchestrator agent microservice using SSE."""
    request_body = {
        "appName": "agent",
        "userId": user_id,
        "sessionId": session_id,
        "newMessage": {
            "role": "user",
            "parts": [{"text": message}]
        },
        "streaming": False
    }
    
    final_text = ""
    async with httpx.AsyncClient(timeout=600.0) as client:
        # Use SSE to match the working reference project pattern
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
        # We use the session_id as the ADK sessionId to keep it consistent
        report = await query_orchestrator(user_id="council_user", session_id=session_id, message=question)

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

# --- Endpoints ---

@app.post("/council/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreate, background_tasks: BackgroundTasks):
    """Create a new research session and trigger the orchestrator."""
    session_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    # Create session document in Firestore
    doc_ref = db.collection("sessions").document(session_id)
    doc_ref.set({
        "session_id": session_id,
        "question": request.question,
        "status": "pending",
        "progress": {"completed_models": 0, "total_models": 3},
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    })

    # Start orchestrator execution in the background
    background_tasks.add_task(run_council_orchestrator, session_id, request.question)

    return {
        "session_id": session_id,
        "status": "pending",
        "created_at": created_at
    }

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
