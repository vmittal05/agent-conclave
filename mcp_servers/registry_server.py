import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
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

# --- In-Memory Storage (Can be moved to Firestore later) ---
# Format: { "agent_name": AgentCard }
registered_agents: Dict[str, AgentCard] = {}

@app.post("/register")
async def register_agent(card: AgentCard):
    """Register or update an agent in the conclave."""
    logger.info(f"Registering agent: {card.name} at {card.url}")
    registered_agents[card.name] = card
    return {"status": "success", "message": f"Agent {card.name} registered."}

@app.post("/lookup")
async def lookup_agents(req: LookupRequest) -> List[AgentCard]:
    """Find agents based on skills or name."""
    results = []
    
    for name, card in registered_agents.items():
        match = True
        if req.agent_name and req.agent_name.lower() not in name.lower():
            match = False
        if req.required_skill:
            skill_found = any(req.required_skill.lower() in s.get("name", "").lower() for s in card.skills)
            if not skill_found:
                match = False
        
        if match:
            results.append(card)
            
    return results

@app.get("/agents")
async def list_all_agents():
    """Returns all currently registered agents."""
    return list(registered_agents.values())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8012)))
