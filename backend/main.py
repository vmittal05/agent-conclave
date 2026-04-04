import os
import uuid
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from google.cloud import firestore
from backend.graph import council_graph
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Multi-Agent Conclave API")

# Initialize Firestore
# Note: Ensure GOOGLE_APPLICATION_CREDENTIALS is set or running in a GCP environment
db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))

# --- Models ---
class SessionCreate(BaseModel):
    question: str

class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str

# --- Graph Execution Logic ---
async def run_council_graph(session_id: str, question: str):
    """Background task to execute the LangGraph workflow."""
    try:
        # Initial State
        initial_state = {
            "session_id": session_id,
            "user_question": question,
            "progress": {"completed_models": 0, "total_models": 3},
            "agent_summaries": [],
            "ready_for_synthesis": False,
            "final_report": ""
        }
        
        # Update Firestore to 'in_progress'
        doc_ref = db.collection("sessions").document(session_id)
        doc_ref.update({"status": "in_progress", "updated_at": firestore.SERVER_TIMESTAMP})

        # Run Graph
        # Use ainvoke for async execution of the compiled graph
        final_state = await council_graph.ainvoke(initial_state)

        # Final Update to Firestore
        doc_ref.update({
            "status": "completed",
            "progress": {"completed_models": 3, "total_models": 3},
            "report_markdown": final_state.get("final_report", ""),
            "updated_at": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Error in graph execution: {e}")
        db.collection("sessions").document(session_id).update({
            "status": "error",
            "error_message": str(e),
            "updated_at": firestore.SERVER_TIMESTAMP
        })

# --- Endpoints ---

@app.post("/council/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreate, background_tasks: BackgroundTasks):
    """Create a new research session and trigger the council graph."""
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

    # Start graph execution in the background
    background_tasks.add_task(run_council_graph, session_id, request.question)

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
