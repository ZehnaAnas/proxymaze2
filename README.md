# ProxyMaze'26 Challenge

This is a full Python implementation of the **Torch Labs ProxyMaze'26 Engineering Challenge**. It provides a real-time HTTP API to manage and monitor a pool of residential proxies, tracking failure rates, triggering alert lifecycles, and dispatching webhook notifications to integrations like Slack and Discord.

## Features

- **Background Monitoring**: Continuously probes proxy endpoints in the background on a configurable interval.
- **Dynamic Configuration**: Adjust request timeouts and check intervals on the fly via the API.
- **Alert Lifecycle Management**: Fires a single alert when the failure rate threshold ($\geq$ 20%) is breached, and automatically resolves it when the pool recovers.
- **Webhook Dispatch**: Robustly delivers event webhooks (`alert.fired`, `alert.resolved`) to standard URLs with retries for transient failures.
- **Integrations**: Supports formatted payloads natively for Slack and Discord.
- **Observability**: Metrics and history tracking for endpoints.

## Prerequisites

- Python 3.8+ (Designed and tested with modern Python 3.x)
- Dependencies listed in `requirements.txt`

## Installation

1. Navigate to the project directory:
   ```bash
   cd proxymaze
   ```
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Start the FastAPI application using the `uvicorn` ASGI server:

```bash
uvicorn main:app --reload
```

The application will be running at `http://127.0.0.1:8000`.

### Interactive API Docs
FastAPI automatically generates interactive Swagger documentation. You can access it by navigating to:
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Running the Tests

A self-contained test script (`test_proxymaze.py`) is provided. It spins up a dummy proxy server, a dummy webhook receiver, and the application server automatically to simulate a test flow.

```bash
python test_proxymaze.py
```

## Architecture

- **`main.py`**: API Routing and Endpoint definitions.
- **`models.py`**: Pydantic models for request/response serialization and validation.
- **`state.py`**: A thread-safe, in-memory datastore leveraging `asyncio.Lock()`.
- **`monitor.py`**: The background asynchronous loop responsible for HTTP probes.
- **`notifier.py`**: Webhook dispatcher implementing failure retries and Slack/Discord specific formatting.
