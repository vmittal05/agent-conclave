import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Search MCP Server (Tavily)")

# --- Configuration ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

@app.post("/tools/search")
async def search(req: SearchRequest):
    """Perform a live web search using Tavily API."""
    logger.info(f"Received search request for query: {req.query}")
    
    if not TAVILY_API_KEY:
        logger.warning("Tavily API Key missing, returning mock data.")
        return {
            "results": [
                {
                    "url": "https://cloud.google.com/docs",
                    "title": "Google Cloud Documentation",
                    "snippet": f"Found results for {req.query}. (Mock Data - Configure TAVILY_API_KEY for live results)",
                    "source_type": "web"
                }
            ]
        }

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": req.query,
        "search_depth": "smart",
        "max_results": req.top_k
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=20.0)
            
            if response.status_code != 200:
                logger.error(f"Tavily API Error ({response.status_code}): {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Tavily API Error: {response.text}")
            
            data = response.json()
            items = data.get("results", [])
            
            results = []
            for item in items:
                results.append({
                    "url": item.get("url"),
                    "title": item.get("title"),
                    "snippet": item.get("content"),
                    "source_type": "web"
                })
            
            logger.info(f"Successfully fetched {len(results)} live results from Tavily.")
            return {"results": results}
    except httpx.TimeoutException:
        logger.error("Tavily API timed out.")
        raise HTTPException(status_code=504, detail="Search API timeout")
    except Exception as e:
        logger.error(f"Unexpected error in search tool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8011)))
