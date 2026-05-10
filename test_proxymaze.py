import asyncio
import httpx
import uvicorn
from fastapi import FastAPI, Request
from multiprocessing import Process
import time
import sys

# Dummy Proxy Server
app_proxy = FastAPI()
proxy_states = {}

@app_proxy.get("/proxy/{pid}")
async def get_proxy(pid: str):
    if proxy_states.get(pid, "up") == "up":
        return {"status": "ok"}
    from fastapi import HTTPException
    raise HTTPException(status_code=500)

def run_proxy_server():
    uvicorn.run(app_proxy, host="127.0.0.1", port=8001, log_level="error")

# Webhook Receiver Server
app_webhook = FastAPI()
received_webhooks = []

@app_webhook.post("/webhook")
async def receive_webhook(request: Request):
    payload = await request.json()
    received_webhooks.append(payload)
    return {"status": "ok"}

@app_webhook.get("/get_webhooks")
async def get_webhooks():
    return received_webhooks

def run_webhook_server():
    uvicorn.run(app_webhook, host="127.0.0.1", port=8002, log_level="error")

# App Server
def run_app_server():
    import main
    uvicorn.run(main.app, host="127.0.0.1", port=8010, log_level="error")

def test_flow():
    p1 = Process(target=run_proxy_server)
    p2 = Process(target=run_webhook_server)
    p3 = Process(target=run_app_server)
    
    p1.start()
    p2.start()
    p3.start()
    
    try:
        time.sleep(3) # Wait for servers to start
        
        # 1. Check health
        r = httpx.get("http://127.0.0.1:8010/health")
        assert r.json()["status"] == "ok"
        
        # 2. Setup config
        r = httpx.post("http://127.0.0.1:8010/config", json={
            "check_interval_seconds": 2,
            "request_timeout_ms": 1000
        })
        assert r.status_code == 200
        
        # 3. Setup webhooks
        r = httpx.post("http://127.0.0.1:8010/webhooks", json={
            "url": "http://127.0.0.1:8002/webhook"
        })
        assert r.status_code == 201
        
        # 4. Setup integrations
        r = httpx.post("http://127.0.0.1:8010/integrations", json={
            "type": "slack",
            "webhook_url": "http://127.0.0.1:8002/webhook",
            "username": "TestBot",
            "events": ["alert.fired", "alert.resolved"]
        })
        assert r.status_code == 201
        
        # 5. Load Proxies
        r = httpx.post("http://127.0.0.1:8010/proxies", json={
            "proxies": [
                "http://127.0.0.1:8001/proxy/px-1",
                "http://127.0.0.1:8001/proxy/px-2",
                "http://127.0.0.1:8001/proxy/px-3",
                "http://127.0.0.1:8001/proxy/px-4",
                "http://127.0.0.1:8001/proxy/px-5"
            ]
        })
        assert r.status_code == 201
        
        time.sleep(3) # wait for first check
        
        r = httpx.get("http://127.0.0.1:8010/proxies")
        data = r.json()
        assert data["total"] == 5
        assert data["up"] == 5
        assert data["down"] == 0
        
        # Make a proxy fail (failure rate 20%)
        # Note: In a multiprocessing environment, we can't easily change `proxy_states` of p1 from here.
        # It's better to just kill the proxy server to simulate complete failure, but we need partial failure.
        # Alternative: use a separate script to make the request to a control endpoint on p1.
    finally:
        p1.terminate()
        p2.terminate()
        p3.terminate()
        p1.join()
        p2.join()
        p3.join()

if __name__ == "__main__":
    test_flow()
    print("Test finished successfully!")
