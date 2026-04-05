import os
import asyncio
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import firestore
from google.cloud.sql.connector import Connector, IPTypes
import sqlalchemy
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Database MCP Server")

# --- Configuration ---
INSTANCE_CONNECTION_NAME = os.getenv("CLOUD_SQL_INSTANCE_CONNECTION_NAME")
DB_USER = os.getenv("CLOUD_SQL_DB_USER")
DB_PASS = os.getenv("CLOUD_SQL_DB_PASSWORD")
DB_NAME = os.getenv("CLOUD_SQL_DB_NAME")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")

# --- Clients Initialization (Lazy) ---
db_engine = None
firestore_client = None

def get_firestore_client():
    global firestore_client
    if firestore_client is None:
        firestore_client = firestore.Client(project=GCP_PROJECT_ID)
    return firestore_client

def get_db_engine():
    global db_engine
    if db_engine is None:
        try:
            connector = Connector()
            def getconn():
                conn = connector.connect(
                    INSTANCE_CONNECTION_NAME,
                    "pg8000",
                    user=DB_USER,
                    password=DB_PASS,
                    db=DB_NAME,
                    ip_type=IPTypes.PUBLIC
                )
                return conn

            db_engine = sqlalchemy.create_engine(
                "postgresql+pg8000://",
                creator=getconn,
            )
            logger.info("Cloud SQL Engine initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Cloud SQL Engine: {e}")
            raise e
    return db_engine

# --- Models ---
class QueryRequest(BaseModel):
    sql: str
    params: Optional[Dict[str, Any]] = None

class FirestoreGetRequest(BaseModel):
    collection: str
    doc_id: str

class FirestoreUpdateRequest(BaseModel):
    collection: str
    doc_id: str
    data: Dict[str, Any]

# --- MCP Tools Implementation ---

@app.post("/tools/sql_query")
async def sql_query(req: QueryRequest):
    """Execute a SQL query with immediate commit."""
    logger.info(f"Executing SQL Query: {req.sql} with params {req.params}")
    engine = get_db_engine()
    try:
        # Use engine.begin() to ensure the transaction is committed
        with engine.begin() as conn:
            result = conn.execute(text(req.sql), req.params or {})
            if result.returns_rows:
                rows = [dict(row._mapping) for row in result]
                return {"results": rows}
            else:
                return {"results": [], "rowcount": result.rowcount}
    except Exception as e:
        logger.error(f"SQL Query Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/sql_execute")
async def sql_execute(req: QueryRequest):
    """Execute a write SQL statement (INSERT/UPDATE)."""
    logger.info(f"Executing SQL Statement: {req.sql} with params {req.params}")
    engine = get_db_engine()
    try:
        with engine.begin() as conn:
            result = conn.execute(text(req.sql), req.params or {})
            return {"rowcount": result.rowcount}
    except Exception as e:
        logger.error(f"SQL Execute Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/firestore_get")
async def firestore_get(req: FirestoreGetRequest):
    """Retrieve a document from Firestore."""
    client = get_firestore_client()
    try:
        doc_ref = client.collection(req.collection).document(req.doc_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            return {"error": "Document not found"}
    except Exception as e:
        logger.error(f"Firestore Get Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/firestore_update")
async def firestore_update(req: FirestoreUpdateRequest):
    """Update a document in Firestore."""
    client = get_firestore_client()
    try:
        doc_ref = client.collection(req.collection).document(req.doc_id)
        doc_ref.set(req.data, merge=True)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Firestore Update Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/get_session_citations")
async def get_session_citations(req: Dict[str, str]):
    """Fetch citations for a session with overlap analysis."""
    session_id = req.get("session_id")
    logger.info(f"Fetching citations for session: {session_id}")
    engine = get_db_engine()
    
    sql = """
        SELECT 
            c.source_url, 
            c.title, 
            MIN(c.snippet) as snippet, 
            COUNT(DISTINCT mr.agent_name) as model_overlap_count,
            STRING_AGG(DISTINCT mr.agent_name, ', ') as citing_agents
        FROM citations c
        JOIN model_runs mr ON c.model_run_id = mr.id
        WHERE mr.session_id = :session_id
        GROUP BY c.source_url, c.title
        ORDER BY model_overlap_count DESC;
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), {"session_id": session_id})
            rows = [dict(row._mapping) for row in result]
            return {"results": rows}
    except Exception as e:
        logger.error(f"Get Session Citations Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8010)))
