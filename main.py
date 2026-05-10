from fastapi import FastAPI, HTTPException, status
from typing import List, Dict
import asyncio
import uuid
import re

from models import (
    HealthResponse, ConfigModel, LoadProxiesRequest, LoadProxiesResponse,
    ProxyModel, ProxyDetailModel, ProxyListResponse, HistoryEntry,
    AlertModel, WebhookRequest, WebhookResponse, IntegrationRequest,
    MetricsModel
)
from state import state
from monitor import monitor_loop

app = FastAPI(title="ProxyMaze'26 API")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_loop())

@app.get("/health", response_model=HealthResponse)
async def get_health():
    return HealthResponse(status="ok")

@app.post("/config", response_model=ConfigModel)
async def set_config(config: ConfigModel):
    async with state.lock:
        state.config = config
    return config

@app.get("/config", response_model=ConfigModel)
async def get_config():
    async with state.lock:
        return state.config

def get_proxy_id_from_url(url: str) -> str:
    # "For a proxy URL whose path ends in a final segment, that segment is the proxy id"
    # Example: https://proxy-provider.example/proxy/px-101 -> px-101
    return url.strip("/").split("/")[-1]

@app.post("/proxies", response_model=LoadProxiesResponse, status_code=201)
async def load_proxies(req: LoadProxiesRequest):
    async with state.lock:
        if req.replace:
            state.proxies.clear()
            
        accepted_proxies = []
        for url in req.proxies:
            pid = get_proxy_id_from_url(url)
            proxy_detail = ProxyDetailModel(
                id=pid,
                url=url,
                status="pending",
                last_checked_at=None,
                consecutive_failures=0,
                total_checks=0,
                uptime_percentage=0.0,
                history=[]
            )
            state.proxies[pid] = proxy_detail
            accepted_proxies.append(ProxyModel(
                id=pid,
                url=url,
                status="pending",
                last_checked_at=None,
                consecutive_failures=0
            ))
            
        return LoadProxiesResponse(
            accepted=len(accepted_proxies),
            proxies=accepted_proxies
        )

@app.get("/proxies", response_model=ProxyListResponse)
async def get_proxies():
    async with state.lock:
        proxies_list = list(state.proxies.values())
        total = len(proxies_list)
        up = sum(1 for p in proxies_list if p.status == "up")
        down = sum(1 for p in proxies_list if p.status == "down")
        failure_rate = round(down / total, 2) if total > 0 else 0.0
        
        basic_proxies = [
            ProxyModel(
                id=p.id,
                url=p.url,
                status=p.status,
                last_checked_at=p.last_checked_at,
                consecutive_failures=p.consecutive_failures
            ) for p in proxies_list
        ]
        
        return ProxyListResponse(
            total=total,
            up=up,
            down=down,
            failure_rate=failure_rate,
            proxies=basic_proxies
        )

@app.get("/proxies/{proxy_id}", response_model=ProxyDetailModel)
async def get_proxy(proxy_id: str):
    async with state.lock:
        if proxy_id not in state.proxies:
            raise HTTPException(status_code=404, detail="Proxy not found")
        return state.proxies[proxy_id]

@app.get("/proxies/{proxy_id}/history", response_model=List[HistoryEntry])
async def get_proxy_history(proxy_id: str):
    async with state.lock:
        if proxy_id not in state.proxies:
            raise HTTPException(status_code=404, detail="Proxy not found")
        return state.proxies[proxy_id].history

@app.delete("/proxies", status_code=204)
async def delete_proxies():
    async with state.lock:
        state.proxies.clear()

@app.get("/alerts", response_model=List[AlertModel])
async def get_alerts():
    async with state.lock:
        return state.alerts

@app.post("/webhooks", response_model=WebhookResponse, status_code=201)
async def register_webhook(req: WebhookRequest):
    async with state.lock:
        webhook_id = f"wh-{uuid.uuid4().hex[:8]}"
        res = WebhookResponse(webhook_id=webhook_id, url=req.url)
        state.webhooks[webhook_id] = res
        return res

@app.post("/integrations", status_code=201)
async def register_integration(req: IntegrationRequest):
    async with state.lock:
        state.integrations.append(req)
        return {"status": "created"}

@app.get("/metrics", response_model=MetricsModel)
async def get_metrics():
    async with state.lock:
        return state.get_metrics()

