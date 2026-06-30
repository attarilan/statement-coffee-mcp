import os
import json
import urllib.parse
import requests
import uvicorn
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Statement Coffee ESB Core")

ESB_BASE_URL = os.getenv("ESB_BASE_URL", "https://services.esb.co.id/core").rstrip("/")
ESB_USERNAME = os.getenv("ESB_USERNAME", "")
ESB_PASSWORD = os.getenv("ESB_PASSWORD", "")

CORS_HEADERS = [
    (b"access-control-allow-origin", b"*"),
    (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
    (b"access-control-allow-headers", b"content-type, authorization"),
]

def get_esb_token():
    login_url = f"{ESB_BASE_URL}/auth/login"
    payload = {"username": ESB_USERNAME, "password": ESB_PASSWORD}
    try:
        response = requests.post(login_url, json=payload, timeout=10)
        if response.status_code == 200:
            result_data = response.json().get("result", {})
            if isinstance(result_data, dict):
                token = result_data.get("token") or result_data.get("accessToken")
                if token:
                    return token
        return None
    except Exception:
        return None

async def read_body(receive):
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return body

async def json_response(send, data, status=200):
    body = json.dumps(data).encode()
    headers = CORS_HEADERS + [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})

@mcp.tool()
def get_daily_sales(branch_id: str, date_from: str, date_to: str = "") -> str:
    """Get Simple Sales transactions for a Statement Coffee branch. Use dateFrom and dateTo in YYYY-MM-DD format. date_to defaults to same as date_from if not provided."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    if not date_to:
        date_to = date_from
    url = f"{ESB_BASE_URL}/sales/simple-product-sales"
    params = {"branchID": branch_id, "dateFrom": date_from, "dateTo": date_to, "limit": 100}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return f"Sales data: {response.json().get('result', 'No result found')}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def check_stock_movement(start_period: str, end_period: str = "", branch_code: str = "", product_name: str = "") -> str:
    """Get stock movement report from ESB Core. Use start_period and end_period in YYYY-MM-DD format. branch_code and product_name are optional filters."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    if not end_period:
        end_period = start_period
    url = f"{ESB_BASE_URL}/report/stock-movement"
    params = {"startPeriod": start_period, "endPeriod": end_period, "limit": 100}
    if branch_code:
        params["branchCode"] = branch_code
    if product_name:
        params["productName"] = product_name
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return f"Stock movement data: {response.json().get('result', 'No result found')}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def list_bill_of_materials(product_name: str = "", bom_id: str = "", flag_active: str = "1") -> str:
    """List Bill of Materials from ESB Core. Optionally filter by product_name, bom_id, or flag_active (1=Active, 2=Not Active)."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    url = f"{ESB_BASE_URL}/product/bom"
    params = {"limit": 100, "flagActive": flag_active}
    if product_name:
        params["productName"] = product_name
    if bom_id:
        params["bomID"] = bom_id
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return f"Bill of Materials list: {response.json().get('result', 'No data found')}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def get_bill_of_material_detail(bom_id: str) -> str:
    """Get full detail of a specific Bill of Material by its ID from ESB Core."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    url = f"{ESB_BASE_URL}/product/bom/{bom_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return f"BOM detail: {response.json().get('result', 'No data found')}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

# Build the MCP app
mcp_asgi = mcp.streamable_http_app()

class MCPWrapper:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

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

        if path == "/api/stock":
            if method == "OPTIONS":
                await send({"type": "http.response.start", "status": 200,
                            "headers": CORS_HEADERS + [(b"content-length", b"0")]})
                await send({"type": "http.response.body", "body": b""})
                return
            qs = urllib.parse.parse_qs(scope.get("query_string", b"").decode())
            product_id = qs.get("productID", [None])[0]
            branch_id  = qs.get("branchID",  ["2"])[0]
            date_str   = qs.get("date",       [""])[0]
            if not date_str:
                from datetime import date
                date_str = date.today().isoformat()
            if not product_id:
                await json_response(send, {"error": "productID required"}, 400)
                return
            token = get_esb_token()
            if not token:
                await json_response(send, {"error": "ESB auth failed"}, 500)
                return
            try:
                url = f"{ESB_BASE_URL}/stock/stock-movement"
                params = {"productID": product_id, "branchID": branch_id,
                          "documentDateFrom": date_str, "documentDateTo": date_str, "limit": 1}
                r = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                                 params=params, timeout=15)
                await json_response(send, r.json(), r.status_code)
            except Exception as e:
                await json_response(send, {"error": str(e)}, 500)
            return

        if path == "/api/purchase-request":
            if method == "OPTIONS":
                await send({"type": "http.response.start", "status": 200,
                            "headers": CORS_HEADERS + [(b"content-length", b"0")]})
                await send({"type": "http.response.body", "body": b""})
                return
            body_bytes = await read_body(receive)
            try:
                body_data = json.loads(body_bytes)
            except Exception:
                await json_response(send, {"error": "Invalid JSON body"}, 400)
                return
            token = get_esb_token()
            if not token:
                await json_response(send, {"error": "ESB auth failed"}, 500)
                return
            try:
                url = f"{ESB_BASE_URL}/purchase/purchase-request"
                r = requests.post(url,
                                  headers={"Authorization": f"Bearer {token}",
                                           "Content-Type": "application/json"},
                                  json=body_data, timeout=30)
                await json_response(send, r.json(), r.status_code)
            except Exception as e:
                await json_response(send, {"error": str(e)}, 500)
            return

        port = int(os.getenv("PORT", 8000))
        patched_headers = []
        for key, value in scope.get("headers", []):
            if key.lower() == b"host":
                patched_headers.append((b"host", f"localhost:{port}".encode()))
            else:
                patched_headers.append((key, value))
        scope = dict(scope)
        scope["headers"] = patched_headers
        await self.app(scope, receive, send)


app = MCPWrapper(mcp_asgi)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
