import os
import requests
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

# 1. Initialize the Claude Connector Server
mcp = FastMCP("Statement Coffee ESB Core")

# Pull settings securely from the Render dashboard variables
ESB_BASE_URL = os.getenv("ESB_BASE_URL", "https://services.esb.co.id/core").rstrip("/")
ESB_USERNAME = os.getenv("ESB_USERNAME", "")
ESB_PASSWORD = os.getenv("ESB_PASSWORD", "")

def get_esb_token():
    """
    Logs into the official ESB Core /auth/login endpoint dynamically
    using Statement Coffee's user credentials.
    """
    login_url = f"{ESB_BASE_URL}/auth/login"
    payload = {
        "username": ESB_USERNAME,
        "password": ESB_PASSWORD
    }
    
    try:
        response = requests.post(login_url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            result_data = data.get("result", {})
            # Look inside the data envelope for the active access token
            if isinstance(result_data, dict):
                token = result_data.get("accessToken")
                if token:
                    return token
        raise Exception(f"Login failed with status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Authentication Failure: {str(e)}")
        return None

# 2. Tool: Fetch Sales Reports
@mcp.tool()
def get_daily_sales(branch_id: str, report_date: str) -> str:
    """
    Fetches daily sales summary for a specific Statement Coffee branch from ESB Core.
    report_date format: YYYY-MM-DD
    """
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

# 3. Tool: Check Stock Levels
@mcp.tool()
def check_item_stock(branch_id: str, search_query: str = "") -> str:
    """
    Queries ESB Core Inventory to get real-time stock counts for items like Beans, Milk, or Syrups.
    """
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

# Wrap the connector into a web app channel
app = Starlette(routes=[Mount("/", app=mcp.sse_app())])

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
