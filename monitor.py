import asyncio
import httpx
import uuid
from datetime import datetime, timezone
from state import state
from models import HistoryEntry, AlertModel
from notifier import dispatch_webhooks

def format_dt(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

async def check_proxy(client: httpx.AsyncClient, proxy_id: str, proxy_url: str, timeout_ms: int):
    try:
        response = await client.get(proxy_url, timeout=timeout_ms / 1000.0)
        if 200 <= response.status_code < 300:
            return "up"
        else:
            return "down"
    except Exception:
        return "down"

async def monitor_loop():
    # Wait a tiny bit before starting the loop to let the API start
    await asyncio.sleep(1)
    while True:
        async with state.lock:
            config_interval = state.config.check_interval_seconds
            config_timeout = state.config.request_timeout_ms
            proxies_to_check = list(state.proxies.items())
        
        if not proxies_to_check:
            await asyncio.sleep(config_interval)
            continue
            
        async with httpx.AsyncClient() as client:
            tasks = []
            for pid, p in proxies_to_check:
                tasks.append(check_proxy(client, pid, p.url, config_timeout))
            
            results = await asyncio.gather(*tasks)
            
        now_dt = datetime.now(timezone.utc)
        now_str = format_dt(now_dt)
        
        down_count = 0
        total_count = len(proxies_to_check)
        failed_proxy_ids = []
        
        async with state.lock:
            state.total_checks += total_count
            
            for (pid, p), status in zip(proxies_to_check, results):
                proxy = state.proxies.get(pid)
                if not proxy:
                    continue # proxy was deleted during check
                
                proxy.status = status
                proxy.last_checked_at = now_str
                proxy.total_checks += 1
                
                if status == "down":
                    proxy.consecutive_failures += 1
                    down_count += 1
                    failed_proxy_ids.append(pid)
                else:
                    proxy.consecutive_failures = 0
                
                proxy.history.append(HistoryEntry(checked_at=now_str, status=status))
                up_checks = sum(1 for h in proxy.history if h.status == "up")
                proxy.uptime_percentage = round((up_checks / proxy.total_checks) * 100, 1)

            failure_rate = round(down_count / total_count, 2) if total_count > 0 else 0.0
            
            active_alert = next((a for a in state.alerts if a.status == "active"), None)
            
            if failure_rate >= 0.20:
                if not active_alert:
                    alert_id = f"alert-{uuid.uuid4().hex[:8]}"
                    new_alert = AlertModel(
                        alert_id=alert_id,
                        status="active",
                        failure_rate=failure_rate,
                        total_proxies=total_count,
                        failed_proxies=down_count,
                        failed_proxy_ids=failed_proxy_ids,
                        threshold=0.20,
                        fired_at=now_str,
                        message="Proxy pool failure rate exceeded 20% threshold."
                    )
                    state.alerts.append(new_alert)
                    state.total_alerts += 1
                    asyncio.create_task(dispatch_webhooks("alert.fired", new_alert))
                else:
                    # Update active alert to keep it in sync with current pool status
                    active_alert.failure_rate = failure_rate
                    active_alert.total_proxies = total_count
                    active_alert.failed_proxies = down_count
                    active_alert.failed_proxy_ids = failed_proxy_ids
            else:
                if active_alert:
                    active_alert.status = "resolved"
                    active_alert.resolved_at = now_str
                    active_alert.failure_rate = failure_rate
                    active_alert.total_proxies = total_count
                    active_alert.failed_proxies = down_count
                    active_alert.failed_proxy_ids = failed_proxy_ids
                    asyncio.create_task(dispatch_webhooks("alert.resolved", active_alert))

        await asyncio.sleep(config_interval)
