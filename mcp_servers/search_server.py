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

import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/tools/search")
async def search(req: SearchRequest):
    """Perform a web search."""
    logger.info(f"Received search request for query: {req.query}")
    
    # If credentials are missing, we provide a structured mock
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
        logger.warning("Search credentials missing, returning mock data.")
        return {
            "results": [
                {
                    "url": "https://cloud.google.com/docs",
                    "title": "Google Cloud Documentation",
                    "snippet": f"Found results for {req.query}. This is a simulated search response.",
                    "source_type": "web"
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
            response = await client.get(url, params=params, timeout=10.0)
            
            if response.status_code != 200:
                logger.error(f"Google Search API Error ({response.status_code}): {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Google API Error: {response.text}")
            
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
            
            logger.info(f"Successfully fetched {len(results)} results from Google.")
            return {"results": results}
    except httpx.TimeoutException:
        logger.error("Google Search API timed out.")
        raise HTTPException(status_code=504, detail="Search API timeout")
    except Exception as e:
        logger.error(f"Unexpected error in search tool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8001)))
