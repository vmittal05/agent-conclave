import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Agent Registry Service")

# --- Models ---

class AgentCard(BaseModel):
    name: str
    description: str
    url: str
    skills: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = {}

class LookupRequest(BaseModel):
    required_skill: Optional[str] = None
    agent_name: Optional[str] = None

# Initialize Firestore
FIRESTORE_PROJECT_ID = os.getenv("GCP_FIRESTORE_PROJECT_ID") or os.getenv("GCP_PROJECT_ID")
try:
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    logger.info(f"Firestore initialized for project: {FIRESTORE_PROJECT_ID}")
except Exception as e:
    logger.error(f"Failed to initialize Firestore: {e}")
    db = None

@app.post("/register")
async def register_agent(card: AgentCard):
    """Register or update an agent in the conclave."""
    logger.info(f"Registering agent: {card.name} at {card.url}")
    if db:
        try:
            doc_ref = db.collection("registered_agents").document(card.name)
            doc_ref.set(card.model_dump())
        except Exception as e:
            logger.error(f"Firestore error during registration: {e}")
    return {"status": "success", "message": f"Agent {card.name} registered."}

@app.post("/lookup")
async def lookup_agents(req: LookupRequest) -> List[Dict[str, Any]]:
    """Find agents based on skills or name."""
    results = []
    if not db:
        return results
        
    try:
        docs = db.collection("registered_agents").stream()
        for doc in docs:
            card_dict = doc.to_dict()
            card = AgentCard(**card_dict)
            
            match = True
            if req.agent_name and req.agent_name.lower() not in card.name.lower():
                match = False
            if req.required_skill:
                skill_found = any(req.required_skill.lower() in s.get("name", "").lower() for s in card.skills)
                if not skill_found:
                    match = False
            
            if match:
                results.append(card_dict)
    except Exception as e:
        logger.error(f"Firestore lookup error: {e}")
        
    return results

@app.get("/agents")
async def list_all_agents():
    """Returns all currently registered agents."""
    if not db:
        return []
    try:
        docs = db.collection("registered_agents").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Firestore list error: {e}")
        return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8012)))
