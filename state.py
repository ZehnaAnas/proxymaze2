import asyncio
from typing import Dict, List
from models import ConfigModel, ProxyDetailModel, AlertModel, WebhookResponse, IntegrationRequest, MetricsModel

class AppState:
    def __init__(self):
        self.config = ConfigModel()
        self.proxies: Dict[str, ProxyDetailModel] = {}
        self.alerts: List[AlertModel] = []
        self.webhooks: Dict[str, WebhookResponse] = {}
        self.integrations: List[IntegrationRequest] = []
        
        self.total_checks = 0
        self.total_alerts = 0
        self.webhook_deliveries = 0
        
        # Async lock for thread-safe operations during background tasks
        self.lock = asyncio.Lock()
        
    def get_metrics(self) -> MetricsModel:
        active_alerts = sum(1 for a in self.alerts if a.status == "active")
        return MetricsModel(
            total_checks=self.total_checks,
            current_pool_size=len(self.proxies),
            active_alerts=active_alerts,
            total_alerts=self.total_alerts,
            webhook_deliveries=self.webhook_deliveries
        )

# Global singleton state
state = AppState()
