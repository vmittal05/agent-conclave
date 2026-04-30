import os
import asyncio
import threading
from google.adk.a2a import A2a
from agent import root_agent
from a2a_utils import register_agent_with_registry

def main():
    port = int(os.getenv("PORT", 8006))
    server = A2a(root_agent)
    
    # Use PUBLIC_AGENT_URL for registration if available (Cloud Run)
    # Background registration
    def run_registration():
        asyncio.run(register_agent_with_registry("viz_agent", port))
    
    threading.Thread(target=run_registration, daemon=True).start()
    server.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
