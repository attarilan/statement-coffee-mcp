import os
import json
import urllib.parse
import requests
import uvicorn
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Statement Coffee ESB Core")

ESB_BASE_URL = os.getenv("ESB_BASE_URL", "https://services.esb.co.id/core").rstrip("/")
ESB_BASE_URL_EXT = os.getenv("ESB_BASE_URL_EXT", "https://core-api.esb.co.id").rstrip("/")
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
def get_product_detail(product_id: int) -> str:
    """Get full product detail from ESB Core by productID, including all productDetailIDs with their unit names (uomName), flagDefaultPurchase, and flagActive."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    url = f"{ESB_BASE_URL}/product/{product_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return f"Product detail: {response.json().get('result', 'No data found')}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def create_purchase_request(
    branch_id: int,
    purchase_request_date: str,
    required_date: str,
    purchase_request_details: str,
    cost_center_id: int = 0,
    project_id: int = 0,
    request_template_id: int = 0,
    additional_info: str = "",
    is_template: bool = False
) -> str:
    """Create a Purchase Request in ESB Core. purchase_request_details is a JSON array: [{productDetailID, requestProcessID, qty, notes}]"""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    try:
        details = json.loads(purchase_request_details)
    except Exception:
        return "Error: purchase_request_details must be a valid JSON array."
    payload = {
        "branchID": branch_id,
        "purchaseRequestDate": purchase_request_date,
        "requiredDate": required_date,
        "purchaseRequestDetails": details,
        "isTemplate": is_template,
    }
    if cost_center_id: payload["costCenterID"] = cost_center_id
    if project_id: payload["projectID"] = project_id
    if request_template_id: payload["requestTemplateID"] = request_template_id
    if additional_info: payload["additionalInfo"] = additional_info
    url = f"{ESB_BASE_URL}/purchase/purchase-request"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return f"Purchase Request created: {response.json().get('result', response.json())}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def get_daily_sales(branch_id: str, date_from: str, date_to: str = "") -> str:
    """Get Simple Sales transactions for a Statement Coffee branch. Use dateFrom and dateTo in YYYY-MM-DD format."""
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
def list_purchase_requests(
    purchase_request_num: str = "",
    date_from: str = "",
    date_to: str = "",
    branch_ids: str = "",
    status_id: str = ""
) -> str:
    """List Purchase Requests from ESB Core. status_id: 1=New, 2=Rejected, 3=Authorized, 25=Closed, 30=Partially Completed, 31=Completed."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    url = f"{ESB_BASE_URL}/purchase/purchase-request"
    params = {"limit": 50}
    if purchase_request_num: params["purchaseRequestNum"] = purchase_request_num
    if date_from: params["purchaseRequestDateFrom"] = date_from
    if date_to: params["purchaseRequestDateTo"] = date_to
    if branch_ids: params["branchIDs"] = branch_ids
    if status_id: params["statusID"] = status_id
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return f"Purchase Requests: {response.json().get('result', 'No data found')}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def check_stock_movement(start_period: str, end_period: str = "", branch_code: str = "", product_name: str = "") -> str:
    """Get stock movement report from ESB Core. Use start_period and end_period in YYYY-MM-DD format."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    if not end_period:
        end_period = start_period
    url = f"{ESB_BASE_URL}/report/stock-movement"
    params = {"startPeriod": start_period, "endPeriod": end_period, "limit": 100}
    if branch_code: params["branchCode"] = branch_code
    if product_name: params["productName"] = product_name
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
    """List Bill of Materials from ESB Core."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    url = f"{ESB_BASE_URL}/product/bom"
    params = {"limit": 100, "flagActive": flag_active}
    if product_name: params["productName"] = product_name
    if bom_id: params["bomID"] = bom_id
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

@mcp.tool()
def create_bill_of_material(bom_type: str, bom_name: str, bom_cost_total: float, access_type: int, bom_details: str, bom_code: str = "", notes: str = "", bom_costs: str = "") -> str:
    """Create a new Bill of Material. bom_type: 'menu', 'assembly', or 'disassembly'."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    bom_type_map = {"menu": 3, "assembly": 1, "disassembly": 2}
    bom_type_id = bom_type_map.get(bom_type.lower())
    if bom_type_id is None:
        return "Error: bom_type must be 'menu', 'assembly', or 'disassembly'."
    try:
        details = json.loads(bom_details)
    except Exception:
        return "Error: bom_details must be a valid JSON array."
    payload = {"bomTypeID": bom_type_id, "bomName": bom_name, "bomCostTotal": bom_cost_total, "accessType": access_type, "selectedUserAccess": [], "bomDetails": details}
    if bom_code: payload["bomCode"] = bom_code
    if notes: payload["notes"] = notes
    if bom_costs:
        try: payload["bomCosts"] = json.loads(bom_costs)
        except Exception: return "Error: bom_costs must be a valid JSON array."
    url = f"{ESB_BASE_URL}/product/bom"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return f"BOM created: {response.json().get('result', response.json())}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def update_bill_of_material(bom_id: str, bom_type: str, bom_name: str, bom_cost_total: float, access_type: int, bom_details: str, bom_code: str = "", product_detail_id: int = 0, notes: str = "", bom_costs: str = "") -> str:
    """Update an existing Bill of Material by its ID."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    bom_type_map = {"menu": 3, "assembly": 1, "disassembly": 2}
    bom_type_id = bom_type_map.get(bom_type.lower())
    if bom_type_id is None:
        return "Error: bom_type must be 'menu', 'assembly', or 'disassembly'."
    try:
        details = json.loads(bom_details)
    except Exception:
        return "Error: bom_details must be a valid JSON array."
    payload = {"bomTypeID": bom_type_id, "bomName": bom_name, "bomCostTotal": bom_cost_total, "accessType": access_type, "selectedUserAccess": [], "bomDetails": details}
    if bom_code: payload["bomCode"] = bom_code
    if notes: payload["notes"] = notes
    if product_detail_id: payload["productDetailID"] = product_detail_id
    if bom_costs:
        try: payload["bomCosts"] = json.loads(bom_costs)
        except Exception: return "Error: bom_costs must be a valid JSON array."
    url = f"{ESB_BASE_URL}/product/bom/{bom_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return f"BOM updated: {response.json().get('result', response.json())}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def create_assembly_actual(simple_manufacturing_date: str, branch_id: int, origin_location_id: int, destination_location_id: int, manufacturing_details: str, manufacturing_materials: str) -> str:
    """Create a Simple Manufacturing Assembly Actual Costing in ESB Core."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    try:
        details = json.loads(manufacturing_details)
        materials = json.loads(manufacturing_materials)
    except Exception:
        return "Error: manufacturing_details and manufacturing_materials must be valid JSON arrays."
    payload = {"simpleManufacturingDate": simple_manufacturing_date, "branchID": branch_id, "originLocationID": origin_location_id, "destinationLocationID": destination_location_id, "simpleManufacturingDetails": details, "simpleManufacturingMaterials": materials}
    url = f"{ESB_BASE_URL}/production/simple-manufacturing/assembly-actual"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return f"Assembly actual created: {response.json().get('result', response.json())}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def create_disassembly_actual(simple_manufacturing_date: str, branch_id: int, origin_location_id: int, destination_location_id: int, manufacturing_details: str, manufacturing_materials: str) -> str:
    """Create a Simple Manufacturing Disassembly Actual Costing in ESB Core."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    try:
        details = json.loads(manufacturing_details)
        materials = json.loads(manufacturing_materials)
    except Exception:
        return "Error: manufacturing_details and manufacturing_materials must be valid JSON arrays."
    payload = {"simpleManufacturingDate": simple_manufacturing_date, "branchID": branch_id, "originLocationID": origin_location_id, "destinationLocationID": destination_location_id, "simpleManufacturingDetails": details, "simpleManufacturingMaterials": materials}
    url = f"{ESB_BASE_URL}/production/simple-manufacturing/disassembly-actual"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return f"Disassembly actual created: {response.json().get('result', response.json())}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def create_memorial_journal(memorial_journal_num: str, memorial_journal_date: str, debit_lines: str, credit_lines: str, additional_info: str = "") -> str:
    """Create a Memorial Journal entry in ESB Core (uses ext API: core-api.esb.co.id). Debit and credit totals must balance."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    try:
        debit = json.loads(debit_lines)
        credit = json.loads(credit_lines)
    except Exception:
        return "Error: debit_lines and credit_lines must be valid JSON arrays."
    payload = {"memorialJournalNum": memorial_journal_num, "memorialJournalDate": memorial_journal_date, "debit": debit, "credit": credit}
    if additional_info: payload["additionalInfo"] = additional_info
    url = f"{ESB_BASE_URL_EXT}/extv1/memorial-journal"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return f"Memorial journal created: {response.json().get('result', response.json())}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def update_bom_name(bom_id: str, new_bom_name: str) -> str:
    """Update a Bill of Material name by bomID. Format: [Department] - [BOM Type] - [Noun]"""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    get_url = f"{ESB_BASE_URL}/product/bom/{bom_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        get_response = requests.get(get_url, headers=headers, timeout=15)
        if get_response.status_code != 200:
            return f"ESB Error {get_response.status_code}: Could not fetch BOM {bom_id}"
        bom_data = get_response.json().get('result', {})
        if not bom_data:
            return f"ERROR: BOM {bom_id} not found"
        def safe_int(val, default=0):
            try: return int(val) if val not in (None, '') else default
            except: return default
        def safe_float(val, default=0.0):
            try: return float(val) if val not in (None, '') else default
            except: return default
        update_payload = {
            "bomName": new_bom_name,
            "bomCode": bom_data.get('bomCode') or '',
            "bomTypeID": safe_int(bom_data.get('bomTypeID'), 3),
            "productDetailID": bom_data.get('productDetailID') or None,
            "notes": bom_data.get('notes') or '',
            "bomCostTotal": safe_float(bom_data.get('bomCostTotal'), 0),
            "accessType": safe_int(bom_data.get('accessType'), 0),
            "bomDetails": bom_data.get('bomDetails') or [],
            "bomCosts": bom_data.get('bomCosts') or [],
            "selectedUserAccess": bom_data.get('selectedUserAccess') or []
        }
        put_response = requests.put(get_url, json=update_payload, headers=headers, timeout=15)
        if put_response.status_code == 200:
            return f"SUCCESS: BOM {bom_id} renamed to '{new_bom_name}'"
        return f"ESB Error {put_response.status_code}: {put_response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def list_products(product_name: str = "", category_id: str = "", flag_active: str = "1", limit: str = "100") -> str:
    """List Products from ESB Core Master Product catalogue."""
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
    url = f"{ESB_BASE_URL}/product/list"
    params = {"limit": int(limit) if limit else 100}
    if product_name: params["productName"] = product_name
    if category_id: params["categoryID"] = int(category_id)
    if flag_active != "": params["flagActive"] = int(flag_active)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return f"Products: {response.json().get('result', 'No data found')}"
        return f"ESB Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"

@mcp.tool()
def get_pos_sales_information(sales_date_from: str, sales_date_to: str, branch_code: str = "", self_order_id: str = "", page: int = 1) -> str:
    """Get per-item POS sales information from ESB OMS. sales_date_from and sales_date_to in YYYY-MM-DD format."""
    import base64
    credentials = base64.b64encode(f"{ESB_USERNAME}:{ESB_PASSWORD}".encode()).decode()
    headers = {"Authorization": f"Basic {credentials}", "Content-Type": "application/json"}
    body = {"filterSalesDateFrom": sales_date_from, "filterSalesDateTo": sales_date_to, "filterBranchCode": branch_code, "filterSelfOrderID": self_order_id}
    url = f"https://int-erp.esb.co.id/external/sales/get-sales-information?page={page}"
    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
        if response.status_code == 200:
            return json.dumps({"page": response.headers.get("X-Pagination-Current-Page", page), "totalPages": response.headers.get("X-Pagination-Page-Count", "?"), "totalCount": response.headers.get("X-Pagination-Total-Count", "?"), "sales": response.json()})
        return f"OMS Error {response.status_code}: {response.text}"
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

        # ── Proxy: GET /api/stock ──────────────────────────────────────────
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
                def fetch_stock(start, end):
                    return requests.get(
                        f"{ESB_BASE_URL}/report/stock-movement",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"startPeriod": start, "endPeriod": end,
                                "branchID": branch_id, "limit": 100},
                        timeout=15
                    )
                r = fetch_stock(date_str, date_str)
                items = (r.json().get("result") or {}).get("data") or []
                match = next((x for x in items if str(x.get("productID")) == str(product_id)), None)
                if not match:
                    from datetime import date, timedelta
                    week_ago = (date.fromisoformat(date_str) - timedelta(days=7)).isoformat()
                    r2 = fetch_stock(week_ago, date_str)
                    items2 = (r2.json().get("result") or {}).get("data") or []
                    candidates = [x for x in items2 if str(x.get("productID")) == str(product_id)]
                    match = candidates[-1] if candidates else None
                payload = {"result": [match]} if match else {"result": [], "message": "not found"}
                await json_response(send, payload, 200)
            except Exception as e:
                await json_response(send, {"error": str(e)}, 500)
            return

        # ── Proxy: POST /api/purchase-request ─────────────────────────────
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
                r = requests.post(
                    f"{ESB_BASE_URL}/purchase/purchase-request",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=body_data, timeout=30
                )
                await json_response(send, r.json(), r.status_code)
            except Exception as e:
                await json_response(send, {"error": str(e)}, 500)
            return

        # Fix host header for MCP security check
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
