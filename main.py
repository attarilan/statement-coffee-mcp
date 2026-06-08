import os
import json
import requests
import uvicorn
from mcp.server.fastmcp import FastMCP
 
mcp = FastMCP("Statement Coffee ESB Core")
 
ESB_BASE_URL = os.getenv("ESB_BASE_URL", "https://services.esb.co.id/core").rstrip("/")
ESB_BASE_URL_EXT = os.getenv("ESB_BASE_URL_EXT", "https://core-api.esb.co.id").rstrip("/")
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
 
@mcp.tool()
def create_bill_of_material(
    bom_type: str,
    bom_name: str,
    bom_cost_total: float,
    access_type: int,
    bom_details: str,
    bom_code: str = "",
    notes: str = "",
    bom_costs: str = ""
) -> str:
    """
    Create a new Bill of Material in ESB Core.
    bom_type must be 'menu' (3), 'assembly' (1), or 'disassembly' (2).
    bom_details is a JSON array of objects with keys: ID, productDetailID, lastHPP, qty, yieldPercent, printGroup (opt).
    bom_costs is an optional JSON array with keys: ID, costDescription, coaNo, costTotal.
    access_type: 0=all users, 1=specific users only.
    """
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
 
    payload = {
        "bomTypeID": bom_type_id,
        "bomName": bom_name,
        "bomCostTotal": bom_cost_total,
        "accessType": access_type,
        "selectedUserAccess": [],
        "bomDetails": details,
    }
    if bom_code:
        payload["bomCode"] = bom_code
    if notes:
        payload["notes"] = notes
    if bom_costs:
        try:
            payload["bomCosts"] = json.loads(bom_costs)
        except Exception:
            return "Error: bom_costs must be a valid JSON array."
 
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
def update_bill_of_material(
    bom_id: str,
    bom_type: str,
    bom_name: str,
    bom_cost_total: float,
    access_type: int,
    bom_details: str,
    bom_code: str = "",
    product_detail_id: int = 0,
    notes: str = "",
    bom_costs: str = ""
) -> str:
    """
    Update an existing Bill of Material in ESB Core by its ID.
    bom_type: 'menu' (3), 'assembly' (1), or 'disassembly' (2).
    bom_details: JSON array of objects with keys: ID, productDetailID, lastHPP, qty, yieldPercent, tolerancePercent, printGroup (opt), weightFactor (opt, required for disassembly).
    bom_costs: optional JSON array with keys: ID, costDescription, coaNo, costTotal.
    product_detail_id: required for assembly/disassembly, optional for menu.
    access_type: 0=all users, 1=specific users only.
    """
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
 
    payload = {
        "bomTypeID": bom_type_id,
        "bomName": bom_name,
        "bomCostTotal": bom_cost_total,
        "accessType": access_type,
        "selectedUserAccess": [],
        "bomDetails": details,
    }
    if bom_code:
        payload["bomCode"] = bom_code
    if notes:
        payload["notes"] = notes
    if product_detail_id:
        payload["productDetailID"] = product_detail_id
    if bom_costs:
        try:
            payload["bomCosts"] = json.loads(bom_costs)
        except Exception:
            return "Error: bom_costs must be a valid JSON array."
 
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
def create_assembly_actual(
    simple_manufacturing_date: str,
    branch_id: int,
    origin_location_id: int,
    destination_location_id: int,
    manufacturing_details: str,
    manufacturing_materials: str
) -> str:
    """
    Create a Simple Manufacturing Assembly Actual Costing in ESB Core.
    simple_manufacturing_date: YYYY-MM-DD format.
    manufacturing_details: JSON array of objects with keys: bomID, productDetailID, productionOrderQty, productionOrderResultQty, notes (opt), expiredDate (opt, YYYY-MM-DD).
    manufacturing_materials: JSON array of objects with keys: productDetailID, systemQty, totalQty.
    """
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
 
    try:
        details = json.loads(manufacturing_details)
        materials = json.loads(manufacturing_materials)
    except Exception:
        return "Error: manufacturing_details and manufacturing_materials must be valid JSON arrays."
 
    payload = {
        "simpleManufacturingDate": simple_manufacturing_date,
        "branchID": branch_id,
        "originLocationID": origin_location_id,
        "destinationLocationID": destination_location_id,
        "simpleManufacturingDetails": details,
        "simpleManufacturingMaterials": materials,
    }
 
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
def create_disassembly_actual(
    simple_manufacturing_date: str,
    branch_id: int,
    origin_location_id: int,
    destination_location_id: int,
    manufacturing_details: str,
    manufacturing_materials: str
) -> str:
    """
    Create a Simple Manufacturing Disassembly Actual Costing in ESB Core.
    simple_manufacturing_date: YYYY-MM-DD format.
    manufacturing_details: JSON array of objects with keys: bomID, productDetailID, productionOrderQty, productionOrderResultQty, notes (opt), expiredDate (opt, YYYY-MM-DD).
    manufacturing_materials: JSON array of objects with keys: productDetailID, systemQty, totalQty.
    """
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
 
    try:
        details = json.loads(manufacturing_details)
        materials = json.loads(manufacturing_materials)
    except Exception:
        return "Error: manufacturing_details and manufacturing_materials must be valid JSON arrays."
 
    payload = {
        "simpleManufacturingDate": simple_manufacturing_date,
        "branchID": branch_id,
        "originLocationID": origin_location_id,
        "destinationLocationID": destination_location_id,
        "simpleManufacturingDetails": details,
        "simpleManufacturingMaterials": materials,
    }
 
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
def create_memorial_journal(
    memorial_journal_num: str,
    memorial_journal_date: str,
    debit_lines: str,
    credit_lines: str,
    additional_info: str = ""
) -> str:
    """
    Create a Memorial Journal entry in ESB Core (uses ext API: core-api.esb.co.id).
    memorial_journal_date: YYYY-MM-DD format.
    debit_lines: JSON array of objects with keys: branchCode, coaNo, currency, rate, amount, notes (opt).
    credit_lines: JSON array of objects with keys: branchCode, coaNo, currency, rate, amount, notes (opt).
    Debit and credit totals must balance.
    """
    token = get_esb_token()
    if not token:
        return "Authentication Failure: Could not get login token from ESB Core."
 
    try:
        debit = json.loads(debit_lines)
        credit = json.loads(credit_lines)
    except Exception:
        return "Error: debit_lines and credit_lines must be valid JSON arrays."
 
    payload = {
        "memorialJournalNum": memorial_journal_num,
        "memorialJournalDate": memorial_journal_date,
        "debit": debit,
        "credit": credit,
    }
    if additional_info:
        payload["additionalInfo"] = additional_info
 
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
    """
    Update a Bill of Material's name by bomID.
    Returns success/failure status. Use this to rename BOMs according to:
    [Department] - [BOM Type] - [Noun]
    Example: "KITCHEN - FOOD - Aglio E Olio"
    """
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
            if val is None or val == '':
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default
 
        def safe_float(val, default=0.0):
            if val is None or val == '':
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
 
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
 
# ── ESB OMS — POS Sales ─────────────────────────────────────────────────────
@mcp.tool()
def get_pos_sales_information(
    sales_date_from: str,
    sales_date_to: str,
    branch_code: str = "",
    status_name: str = "",
    page: int = 1,
    sort_by: str = "",
    sort_order: str = "",
    sales_num: str = "",
    bill_num: str = "",
    self_order_id: str = "",
    ext_branch_code: str = ""
) -> str:
    """
    Get per-item POS sales information synced from ESB local POS systems (ESB OMS).
    Returns transaction-level sales breakdown including items sold, quantities,
    revenue, and bill details per branch.
    sales_date_from and sales_date_to are required, format YYYY-MM-DD.
    branch_code filters by branch (if empty, all branches returned).
    status_name can be: New, Finished, Cancelled, or Void.
    sort_by can be: salesDateIn, salesDateOut, memberCode.
    sort_order can be: asc or desc.
    sales_num and bill_num must be exact matches if provided.
    """
    url = f"{ESB_BASE_URL_EXT}/corev1/sales/sales-information"
    params = {
        "salesDateFrom": sales_date_from,
        "salesDateTo": sales_date_to,
        "page": page,
    }
    if branch_code:
        params["branchCode"] = branch_code
    if status_name:
        params["statusName"] = status_name
    if sort_by:
        params["sortBy"] = sort_by
    if sort_order:
        params["sortOrder"] = sort_order
    if sales_num:
        params["salesNum"] = sales_num
    if bill_num:
        params["billNum"] = bill_num
    if self_order_id:
        params["selfOrderID"] = self_order_id
    if ext_branch_code:
        params["extBranchCode"] = ext_branch_code
 
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.get(url, headers=headers, params=params, auth=(ESB_USERNAME, ESB_PASSWORD), timeout=15)
        if response.status_code == 200:
            return f"POS sales information: {response.json().get('result', response.json())}"
        return f"OMS Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Network error: {str(e)}"
 
# Build the MCP app
mcp_asgi = mcp.streamable_http_app()
 
# Wrapper: fixes host header + handles OAuth discovery + passes lifespan through
class MCPWrapper:
    def __init__(self, app):
        self.app = app
 
    async def __call__(self, scope, receive, send):
        # Pass lifespan through directly so MCP initializes its task group
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
 
        # Fix host header: rewrite Render's public domain to localhost
        # so the MCP library's security check passes
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
