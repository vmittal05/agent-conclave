import os
import httpx
import asyncio
import json
import base64
from dotenv import load_dotenv

load_dotenv()

CODE_URL = "http://localhost:8013"
FS_URL = "http://localhost:8014"
GCS_BUCKET = os.getenv("GCS_BUCKET_NAME", "conclave-assets-apac-h2s")

async def test_pipeline():
    print("--- 1. Testing Code Interpreter MCP ---")
    code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(10,6))
plt.plot(x, y, label='Sine Wave')
plt.title('Isolated Pipeline Test Chart')
plt.grid(True)
plt.savefig('test_chart.png')
print("Chart generated successfully.")
"""
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            res = await client.post(f"{CODE_URL}/tools/execute_python", json={"code": code})
            res.raise_for_status()
            data = res.json()
            images = data.get("generated_images", {})
            
            if not images:
                print("❌ FAILED: No images returned from Code MCP.")
                return
            
            img_name = list(images.keys())[0]
            base64_data = images[img_name]
            print(f"✅ SUCCESS: Captured base64 image ({len(base64_data)} bytes)")
            
            print("\n--- 2. Testing File System MCP ---")
            upload_res = await client.post(f"{FS_URL}/tools/gcs_write", json={
                "file_path": "tests/isolated_test_chart.png",
                "content": base64_data,
                "content_type": "image/png"
            })
            upload_res.raise_for_status()
            upload_data = upload_res.json()
            public_url = upload_data.get("public_url")
            
            print(f"✅ SUCCESS: Uploaded to GCS. Public URL: {public_url}")
            
            print("\n--- 3. Verifying URL Reachability ---")
            check_res = await client.get(public_url)
            if check_res.status_code == 200:
                print(f"✅ SUCCESS: Image is publicly reachable! Content-Type: {check_res.headers.get('Content-Type')}")
            else:
                print(f"❌ FAILED: Image returned {check_res.status_code}. Possible CORS or permission issue.")
                print(f"Error Body: {check_res.text}")

        except Exception as e:
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
