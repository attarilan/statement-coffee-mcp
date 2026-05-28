import os
import requests
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

# 1. Initialize the Claude Connector Server
mcp = FastMCP("Statement Coffee ESB Core")

# Pull our settings securely from the cloud dashboard
ESB_BASE_URL = os.getenv("ESB_BASE_URL", "https://services.esb.co.id/core").rstrip("/")
ESB_STATIC_TOKEN = os.getenv("ESB_STATIC_TOKEN", "")

# 2. Tool: Fetch Sales Reports
@mcp.tool()
def get_daily_sales(branch_id: str, report_date: str) -> str:
    """
    Fetches daily sales summary for a specific Statement Coffee branch from ESB Core.
    report_date format: YYYY-MM-DD
    """
    url = f"{ESB_BASE_URL}/reports/sales"
    params = {"branchID": branch_id, "date": report_date}
    headers = {"Authorization": f"Bearer {ESB_STATIC_TOKEN}", "Content-Type": "application/json"}

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
    url = f"{ESB_BASE_URL}/inventory/stock-status"
    params = {"branchID": branch_id, "search": search_query}
    headers = {"Authorization": f"Bearer {ESB_STATIC_TOKEN}", "Content-Type": "application/json"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return f"Data payload: {response.json().get('result', 'No result data found')}"
        return f"ESB Error: {response.status_code}"
    except Exception as e:
        return f"Network error tracking stock: {str(e)}"

# Turn this script into a secure web application for Claude website
app = Starlette(routes=[Mount("/", app=mcp.sse_app())])

if __name__ == "__main__":
    # Read the automatic port number assigned by Render cloud
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
