import asyncio
import httpx
from datetime import datetime, timezone
from models import AlertModel
from state import state

async def deliver_payload_with_retry(client: httpx.AsyncClient, url: str, payload: dict, timeout=5.0):
    max_time = datetime.now(timezone.utc).timestamp() + 55 # Try for up to 55 seconds
    while datetime.now(timezone.utc).timestamp() < max_time:
        try:
            response = await client.post(url, json=payload, timeout=timeout, headers={"Content-Type": "application/json"})
            if response.status_code in (500, 502, 503, 504):
                await asyncio.sleep(1) # Backoff
                continue
            
            # Successful delivery (or non-transient failure which shouldn't be retried per spec)
            async with state.lock:
                state.webhook_deliveries += 1
            return
        except (httpx.RequestError, httpx.TimeoutException):
            await asyncio.sleep(1)
            continue

async def dispatch_webhooks(event: str, alert: AlertModel):
    async with httpx.AsyncClient() as client:
        tasks = []
        
        # Standard webhooks
        standard_payload = alert.model_dump()
        standard_payload["event"] = event
        for hook in state.webhooks.values():
            tasks.append(deliver_payload_with_retry(client, hook.url, standard_payload))
            
        # Integrations
        for integration in state.integrations:
            if event not in integration.events:
                continue
            
            if integration.type == "slack":
                ts = int(datetime.fromisoformat(alert.fired_at.replace("Z", "+00:00")).timestamp())
                color = "#FF0000" if event == "alert.fired" else "#00FF00"
                
                slack_payload = {
                    "username": integration.username,
                    "text": alert.message,
                    "attachments": [{
                        "color": color,
                        "fields": [
                            {"title": "Alert ID", "value": alert.alert_id, "short": True},
                            {"title": "Failure Rate", "value": str(alert.failure_rate), "short": True},
                            {"title": "Failed Proxies", "value": str(alert.failed_proxies), "short": True},
                            {"title": "Threshold", "value": str(alert.threshold), "short": True},
                            {"title": "Failed IDs", "value": ", ".join(alert.failed_proxy_ids) if alert.failed_proxy_ids else "None", "short": False},
                            {"title": "Fired At", "value": alert.fired_at, "short": False}
                        ],
                        "footer": "ProxyMaze26",
                        "ts": ts
                    }]
                }
                tasks.append(deliver_payload_with_retry(client, integration.webhook_url, slack_payload))
                
            elif integration.type == "discord":
                color = 16711680 if event == "alert.fired" else 65280
                discord_payload = {
                    "username": integration.username,
                    "embeds": [{
                        "title": f"ProxyMaze Event: {event}",
                        "description": alert.message,
                        "color": color,
                        "fields": [
                            {"name": "Alert ID", "value": alert.alert_id, "inline": True},
                            {"name": "Failure Rate", "value": str(alert.failure_rate), "inline": True},
                            {"name": "Failed Proxies", "value": str(alert.failed_proxies), "inline": True},
                            {"name": "Threshold", "value": str(alert.threshold), "inline": True},
                            {"name": "Failed IDs", "value": ", ".join(alert.failed_proxy_ids) if alert.failed_proxy_ids else "None", "inline": False}
                        ],
                        "footer": {"text": "ProxyMaze26"}
                    }]
                }
                tasks.append(deliver_payload_with_retry(client, integration.webhook_url, discord_payload))
                
        if tasks:
            await asyncio.gather(*tasks)

