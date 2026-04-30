import os
import logging
import subprocess
import tempfile
import sys
import shutil
import base64
import glob
from typing import Optional, Dict, Any, List
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
    """Execute Python code in a sandboxed temp directory and return output + generated images."""
    logger.info("Received code execution request.")
    
    # Create a unique working directory for this execution
    work_dir = tempfile.mkdtemp()
    script_path = os.path.join(work_dir, "script.py")
    
    with open(script_path, "w") as f:
        f.write(req.code)

    try:
        # Execute the code in the temp directory
        result = subprocess.run(
            [sys.executable, "script.py"],
            capture_output=True,
            text=True,
            timeout=req.timeout,
            cwd=work_dir,
            env={**os.environ, "MPLBACKEND": "Agg"} 
        )
        
        # Collect generated images (.png)
        images = {}
        for img_path in glob.glob(os.path.join(work_dir, "*.png")):
            with open(img_path, "rb") as f:
                img_name = os.path.basename(img_path)
                images[img_name] = base64.b64encode(f.read()).decode('utf-8')
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "generated_images": images
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail=f"Execution timed out after {req.timeout}s")
    except Exception as e:
        logger.error(f"Execution Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    import uvicorn
    # Default port for Code MCP is 8013
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8013)))
