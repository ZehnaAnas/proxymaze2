from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime, timezone

def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class ConfigModel(BaseModel):
    check_interval_seconds: int = 15
    request_timeout_ms: int = 3000

class HistoryEntry(BaseModel):
    checked_at: str
    status: Literal["up", "down"]

class ProxyModel(BaseModel):
    id: str
    url: str
    status: Literal["up", "down", "pending"]
    last_checked_at: Optional[str] = None
    consecutive_failures: int = 0

class ProxyDetailModel(ProxyModel):
    total_checks: int = 0
    uptime_percentage: float = 0.0
    history: List[HistoryEntry] = []

class ProxyListResponse(BaseModel):
    total: int
    up: int
    down: int
    failure_rate: float
    proxies: List[ProxyModel]

class LoadProxiesRequest(BaseModel):
    proxies: List[str]
    replace: bool = False

    class Config:
        extra = "allow"

class LoadProxiesResponse(BaseModel):
    accepted: int
    proxies: List[ProxyModel]

class AlertModel(BaseModel):
    alert_id: str
    status: Literal["active", "resolved"]
    failure_rate: float
    total_proxies: int
    failed_proxies: int
    failed_proxy_ids: List[str]
    threshold: float = 0.20
    fired_at: str
    resolved_at: Optional[str] = None
    message: str

class WebhookRequest(BaseModel):
    url: str
    
    class Config:
        extra = "allow"

class WebhookResponse(BaseModel):
    webhook_id: str
    url: str

class IntegrationRequest(BaseModel):
    type: Literal["slack", "discord"]
    webhook_url: str
    username: str = "ProxyWatch"
    events: List[str] = ["alert.fired", "alert.resolved"]
    
    class Config:
        extra = "allow"

class MetricsModel(BaseModel):
    total_checks: int
    current_pool_size: int
    active_alerts: int
    total_alerts: int
    webhook_deliveries: int

class HealthResponse(BaseModel):
    status: str = "ok"
