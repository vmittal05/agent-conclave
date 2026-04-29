import os
import logging
import subprocess
import tempfile
import sys
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Code Interpreter MCP Server")

class CodeRequest(BaseModel):
    code: str
    timeout: Optional[int] = 30

@app.post("/tools/execute_python")
async def execute_python(req: CodeRequest):
    """Execute Python code in a subprocess and return stdout/stderr."""
    logger.info("Received code execution request.")
    
    # We use a temporary file to run the code
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
        tmp.write(req.code)
        tmp_path = tmp.name

    try:
        # Execute the code in a subprocess
        # Note: In a real-world scenario, you'd use a more secure sandbox
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=req.timeout,
            env={**os.environ, "MPLBACKEND": "Agg"} # Ensure matplotlib doesn't try to open a window
        )
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        logger.error(f"Code execution timed out after {req.timeout} seconds.")
        raise HTTPException(status_code=408, detail=f"Execution timed out after {req.timeout}s")
    except Exception as e:
        logger.error(f"Unexpected error during code execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    import uvicorn
    # Default port for Code MCP is 8013
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8013)))
