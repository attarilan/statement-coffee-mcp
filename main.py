import os
import json
import requests
import uvicorn
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Statement Coffee ESB Core")

ESB_BASE_URL = os.getenv("ESB_BASE_URL", "https://services.esb.co.id/core").rstrip("/")
ESB_USERNAME = os.getenv("ESB_USERNAME", "")
ESB_PASSWORD = os.getenv("ESB_PASSWORD", "")

def get_esb_token():
    login_url = f"{ESB_BASE_URL}/auth/login"
    payload = {"username": ESB_USERNAME, "password": ESB_PASSWORD}
    try:
        response = requests.post(login_url, json=payload, timeout=10)
        if response.status_code == 200:
            result_data = response.json().get("result", {})
            if isinstance(result_data, dict):
                token = result_data.get("accessToken")
                if token:
                    return token
        return None
    except Exception:
        return None

@mcp.tool()
def get_daily_sales(branch_id: str, report_date: str) -> str:
    """Fetches daily sales summary for a specific Statement Coffee branch from ESB Core (YYYY-MM-DD)."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not generate a login token via ESB Core."
    url = f"{ESB_BASE_URL}/reports/sales"
    params = {"branchID": branch_id, "date": report_date}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return f"Data payload: {response.json().get('result', 'No result data found')}"
        return f"ESB Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Network error linking to ESB: {str(e)}"

@mcp.tool()
def check_item_stock(branch_id: str, search_query: str = "") -> str:
    """Queries ESB Core Inventory to get real-time stock counts for cafe items."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not generate a login token via ESB Core."
    url = f"{ESB_BASE_URL}/inventory/stock-status"
    params = {"branchID": branch_id, "search": search_query}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return f"Data payload: {response.json().get('result', 'No result data found')}"
        return f"ESB Error: {response.status_code}"
    except Exception as e:
        return f"Network error tracking stock: {str(e)}"


# Build the MCP streamable HTTP app
mcp_asgi = mcp.streamable_http_app()

# Lightweight wrapper: intercepts OAuth discovery, passes everything else
# (including lifespan startup) directly to the MCP engine
class MCPWrapper:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Always pass lifespan events through so MCP initializes properly
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # OAuth discovery: tell Claude no sign-in is required
        if path == "/.well-known/oauth-protected-resource" or \
           path.startswith("/.well-known/oauth-protected-resource/"):
            body = json.dumps({
                "resource": "https://statement-coffee-mcp.onrender.com",
                "authorization_servers": []
            }).encode()
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return

        # Everything else (including /mcp) goes to the MCP engine
        await self.app(scope, receive, send)


app = MCPWrapper(mcp_asgi)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
