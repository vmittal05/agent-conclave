import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Search MCP Server")

# --- Configuration ---
# Example: Using Google Custom Search API or Mocking
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 10

@app.post("/tools/search")
async def search(req: SearchRequest):
    """Perform a web search."""
    # If credentials are missing, we provide a structured mock for testing Phase 4/5 logic
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
        return {
            "results": [
                {
                    "url": "https://cloud.google.com/docs",
                    "title": "Google Cloud Documentation",
                    "snippet": f"Found results for {req.query}. This is a simulated search response.",
                    "source_type": "web"
                },
                {
                    "url": "https://en.wikipedia.org/wiki/Multi-agent_system",
                    "title": "Multi-agent systems",
                    "snippet": "A multi-agent system is a computerized system composed of multiple interacting intelligent agents.",
                    "source_type": "academic"
                }
            ]
        }

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_SEARCH_CX,
        "q": req.query,
        "num": min(req.top_k, 10)
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            results = []
            for item in items:
                results.append({
                    "url": item.get("link"),
                    "title": item.get("title"),
                    "snippet": item.get("snippet"),
                    "source_type": "web"
                })
            
            return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8001)))
