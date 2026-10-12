"""
FIWARE Smart Home Web Application
Thesis-faithful reimplementation 2026 of Abdussamad Bello MSc PoC (Atilim, Jan 2022).
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

ORION = os.getenv("ORION_URL", "http://orion:1026").rstrip("/")
IOTA = os.getenv("IOTA_URL", "http://iot-agent:4041").rstrip("/")
QL = os.getenv("QUANTUMLEAP_URL", "http://quantumleap:8668").rstrip("/")
KEYROCK = os.getenv("KEYROCK_URL", "http://keyrock:3005").rstrip("/")
KEYROCK_PUBLIC = os.getenv("KEYROCK_PUBLIC_URL", "http://localhost:3005").rstrip("/")
SERVICE = os.getenv("FIWARE_SERVICE", "smartHome")
SERVICE_PATH = os.getenv("FIWARE_SERVICEPATH", "/")
AUTH_MODE = os.getenv("AUTH_MODE", "keyrock").lower()
CLIENT_ID = os.getenv("OAUTH2_CLIENT_ID", "smart-home-app")
CLIENT_SECRET = os.getenv("OAUTH2_CLIENT_SECRET", "smart-home-secret-change-me")
SECRET_KEY = os.getenv("WEBAPP_SECRET_KEY", secrets.token_hex(16))

DEMO_USERS = {
    os.getenv("DEMO_ADMIN_EMAIL", "homeowner@smarthome.local"): {
        "password": os.getenv("DEMO_ADMIN_PASSWORD", "HomeOwner2022!"),
        "role": "admin",
        "name": "Home Owner",
        "can_toggle": True,
    },
    os.getenv("DEMO_GUEST_EMAIL", "guest@smarthome.local"): {
        "password": os.getenv("DEMO_GUEST_PASSWORD", "GuestView2022!"),
        "role": "guest",
        "name": "Guest Viewer",
        "can_toggle": False,
    },
    os.getenv("IDM_ADMIN_EMAIL", "admin@test.com"): {
        "password": os.getenv("IDM_ADMIN_PASS", "1234"),
        "role": "admin",
        "name": "Keyrock Admin",
        "can_toggle": True,
    },
}

ROOMS = ["LivingRoom", "Bedroom", "Kitchen", "Hallway"]

app = FastAPI(title="FIWARE Smart Home PoC", version="2026.1")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=3600 * 8)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def fiware_headers() -> dict[str, str]:
    return {
        "Fiware-Service": SERVICE,
        "Fiware-ServicePath": SERVICE_PATH,
        "Accept": "application/json",
    }


def current_user(request: Request) -> Optional[dict[str, Any]]:
    return request.session.get("user")


def require_login(request: Request) -> Optional[RedirectResponse]:
    if not current_user(request):
        return RedirectResponse("/login?next=" + request.url.path, status_code=303)
    return None


async def orion_get_entities(type_filter: Optional[str] = None) -> list[dict]:
    params: dict[str, Any] = {"options": "keyValues", "limit": 1000}
    if type_filter:
        params["type"] = type_filter
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{ORION}/v2/entities", headers=fiware_headers(), params=params)
        if r.status_code >= 400:
            return []
        return r.json()


async def orion_update_attrs(entity_id: str, attrs: dict) -> tuple[bool, str]:
    body = {k: {"type": "command" if k in ("on", "off", "open", "close", "ring") else "Text", "value": v} for k, v in attrs.items()}
    # Prefer NGSI attribute update; for commanded devices use command attrs
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.patch(
            f"{ORION}/v2/entities/{entity_id}/attrs",
            headers={**fiware_headers(), "Content-Type": "application/json"},
            json=body,
        )
        if r.status_code in (204, 200):
            return True, "ok"
        return False, r.text or f"HTTP {r.status_code}"


async def send_device_command(device_id: str, command: str, value: Any = None) -> tuple[bool, str]:
    """Send actuator command via Orion NGSI-v2 (IoT Agent registration handles southbound)."""
    # Map UI actions to command attribute names used at provision time
    cmd_map = {
        "bulb_on": ("on", ""),
        "bulb_off": ("off", ""),
        "fan_on": ("on", ""),
        "fan_off": ("off", ""),
        "door_close": ("close", ""),
        "door_open": ("open", ""),
        "bell_ring": ("ring", ""),
        "hvac_set": ("setTemperature", value),
    }
    if command not in cmd_map:
        return False, f"unknown command {command}"
    attr, val = cmd_map[command]
    payload = {attr: {"type": "command", "value": val if val is not None else ""}}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.patch(
            f"{ORION}/v2/entities/{device_id}/attrs",
            headers={**fiware_headers(), "Content-Type": "application/json"},
            json=payload,
        )
        if r.status_code in (204, 200):
            return True, "command sent"
        # Fallback: update state attribute directly (virtual devices without southbound)
        state_updates = {
            "bulb_on": {"state": {"type": "Text", "value": "ON"}, "luminosityTarget": {"type": "Number", "value": 800}},
            "bulb_off": {"state": {"type": "Text", "value": "OFF"}, "luminosityTarget": {"type": "Number", "value": 0}},
            "fan_on": {"state": {"type": "Text", "value": "ON"}},
            "fan_off": {"state": {"type": "Text", "value": "OFF"}},
            "door_close": {"state": {"type": "Text", "value": "CLOSED"}},
            "door_open": {"state": {"type": "Text", "value": "OPEN"}},
            "bell_ring": {"state": {"type": "Text", "value": "RINGING"}, "lastRing": {"type": "DateTime", "value": datetime.utcnow().isoformat() + "Z"}},
            "hvac_set": {"targetTemperature": {"type": "Number", "value": float(value)}, "state": {"type": "Text", "value": "ON"}},
        }
        r2 = await client.post(
            f"{ORION}/v2/entities/{device_id}/attrs?options=keyValues",
            headers={**fiware_headers(), "Content-Type": "application/json"},
            json={k: v["value"] for k, v in state_updates[command].items()},
        )
        # Try structured attrs if keyValues post fails
        if r2.status_code not in (204, 200):
            r3 = await client.patch(
                f"{ORION}/v2/entities/{device_id}/attrs",
                headers={**fiware_headers(), "Content-Type": "application/json"},
                json=state_updates[command],
            )
            if r3.status_code in (204, 200):
                return True, "state updated (direct)"
            return False, (r.text or "") + " | " + (r3.text or f"HTTP {r3.status_code}")
        return True, "state updated (direct)"


async def ql_history(entity_id: str, attr: str, last_n: int = 50) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{QL}/v2/entities/{entity_id}/attrs/{attr}"
        r = await client.get(
            url,
            headers=fiware_headers(),
            params={"lastN": last_n},
        )
        if r.status_code >= 400:
            return []
        data = r.json()
        values: list[dict] = []
        if not isinstance(data, dict):
            return values
        # QuantumLeap NGSI-v2: {"attrName","entityId","index":[...],"values":[...]}
        if "values" in data and "index" in data:
            vals = data.get("values") or []
            idx = data.get("index") or []
            for i, v in enumerate(vals):
                values.append({"t": idx[i] if i < len(idx) else None, "v": v})
            return values
        block = data.get(attr)
        if isinstance(block, dict):
            vals = block.get("values") or []
            idx = block.get("index") or []
            for i, v in enumerate(vals):
                values.append({"t": idx[i] if i < len(idx) else None, "v": v})
            return values
        if isinstance(data.get("data"), list):
            for row in data["data"]:
                values.append(row)
        return values

async def keyrock_password_login(email: str, password: str) -> Optional[dict]:
    """Try Keyrock OAuth2 password grant, then Keyrock auth tokens API."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # Password grant
        try:
            r = await client.post(
                f"{KEYROCK}/oauth2/token",
                data={
                    "grant_type": "password",
                    "username": email,
                    "password": password,
                },
                auth=(CLIENT_ID, CLIENT_SECRET),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if r.status_code == 200:
                tok = r.json()
                return {
                    "email": email,
                    "name": email.split("@")[0],
                    "role": "admin" if "admin" in email or "homeowner" in email else "user",
                    "can_toggle": "guest" not in email,
                    "access_token": tok.get("access_token"),
                    "auth_source": "keyrock_oauth2",
                }
        except Exception:
            pass
        # Auth tokens API (admin style)
        try:
            r = await client.post(
                f"{KEYROCK}/v1/auth/tokens",
                json={"name": email, "password": password},
                headers={"Content-Type": "application/json"},
            )
            if r.status_code in (200, 201):
                token = r.headers.get("X-Subject-Token") or r.json().get("token")
                return {
                    "email": email,
                    "name": email.split("@")[0],
                    "role": "admin",
                    "can_toggle": True,
                    "access_token": token,
                    "auth_source": "keyrock_tokens",
                }
        except Exception:
            pass
    return None


def local_login(email: str, password: str) -> Optional[dict]:
    u = DEMO_USERS.get(email)
    if u and u["password"] == password:
        return {
            "email": email,
            "name": u["name"],
            "role": u["role"],
            "can_toggle": u["can_toggle"],
            "access_token": None,
            "auth_source": "local",
        }
    return None


@app.get("/health")
async def health():
    status = {"app": "ok", "orion": "down", "iot-agent": "down", "quantumleap": "down", "keyrock": "down"}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in [
            ("orion", f"{ORION}/version"),
            ("iot-agent", f"{IOTA}/iot/about"),
            ("quantumleap", f"{QL}/version"),
            ("keyrock", f"{KEYROCK}/version"),
        ]:
            try:
                r = await client.get(url)
                status[name] = "ok" if r.status_code < 500 else f"http_{r.status_code}"
            except Exception as e:
                status[name] = f"unreachable"
    return status


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/devices", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None, next: str = "/devices"):
    if current_user(request):
        return RedirectResponse(next, status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error,
            "next": next,
            "auth_mode": AUTH_MODE,
            "demo_admin": os.getenv("DEMO_ADMIN_EMAIL", "homeowner@smarthome.local"),
            "demo_guest": os.getenv("DEMO_GUEST_EMAIL", "guest@smarthome.local"),
        },
    )


@app.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/devices"),
):
    user = None
    if AUTH_MODE == "keyrock":
        user = await keyrock_password_login(email, password)
        if not user:
            # fallback to local demo users so PoC works without fully provisioned OAuth app
            user = local_login(email, password)
            if user:
                user["auth_source"] = "local_fallback"
    else:
        user = local_login(email, password)

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid username or password (or Keyrock unreachable).",
                "next": next,
                "auth_mode": AUTH_MODE,
                "demo_admin": os.getenv("DEMO_ADMIN_EMAIL", "homeowner@smarthome.local"),
                "demo_guest": os.getenv("DEMO_GUEST_EMAIL", "guest@smarthome.local"),
            },
            status_code=401,
        )
    request.session["user"] = user
    return RedirectResponse(next or "/devices", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request, auth_error: Optional[str] = None):
    user = current_user(request)
    entities = await orion_get_entities()
    by_room: dict[str, list] = {r: [] for r in ROOMS}
    other = []
    for e in entities:
        room = e.get("refRoom") or e.get("room") or "Other"
        if isinstance(room, dict):
            room = room.get("value", "Other")
        item = {
            "id": e.get("id"),
            "type": e.get("type"),
            "state": e.get("state"),
            "temperature": e.get("temperature"),
            "luminosity": e.get("luminosity"),
            "motion": e.get("motion"),
            "targetTemperature": e.get("targetTemperature"),
            "category": e.get("category"),
        }
        if room in by_room:
            by_room[room].append(item)
        else:
            other.append(item)
    return templates.TemplateResponse(
        "devices.html",
        {
            "request": request,
            "user": user,
            "rooms": by_room,
            "other": other,
            "auth_error": auth_error,
            "logged_in": bool(user),
        },
    )


@app.get("/devices/public", response_class=HTMLResponse)
async def devices_logged_out(request: Request):
    """Logged-out device management view (thesis: shows auth error on toggle)."""
    request.session.clear()
    return RedirectResponse("/devices?auth_error=login_required", status_code=303)


@app.post("/devices/{entity_id}/command")
async def device_command(
    request: Request,
    entity_id: str,
    command: str = Form(...),
    value: Optional[str] = Form(None),
):
    user = current_user(request)
    if not user:
        return RedirectResponse("/devices?auth_error=You+must+login+to+control+devices", status_code=303)
    if not user.get("can_toggle"):
        return RedirectResponse(
            "/devices?auth_error=Unauthorized:+guest+role+cannot+toggle+actuators",
            status_code=303,
        )
    ok, msg = await send_device_command(entity_id, command, value)
    if not ok:
        return RedirectResponse(f"/devices?auth_error=Command+failed:+{msg[:80]}", status_code=303)
    return RedirectResponse("/devices", status_code=303)


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, room: Optional[str] = None):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login?next=/history", status_code=303)
    entities = await orion_get_entities()
    sensors = [e for e in entities if e.get("type") in ("MotionSensor", "LuminositySensor", "TemperatureSensor")]
    if room:
        sensors = [e for e in sensors if (e.get("refRoom") or e.get("room")) == room]
    # Build history list entries
    rows = []
    for s in sensors:
        sid = s["id"]
        stype = s["type"]
        attr = {"MotionSensor": "motion", "LuminositySensor": "luminosity", "TemperatureSensor": "temperature"}[stype]
        hist = await ql_history(sid, attr, last_n=20)
        rows.append(
            {
                "id": sid,
                "type": stype,
                "room": s.get("refRoom") or s.get("room"),
                "latest": s.get(attr),
                "history": hist,
                "attr": attr,
            }
        )
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "user": user, "rows": rows, "rooms": ROOMS, "selected_room": room},
    )


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login?next=/reports", status_code=303)
    entities = await orion_get_entities()
    # Pick luminosity + temperature for chart data
    charts = []
    for e in entities:
        if e.get("type") == "LuminositySensor":
            hist = await ql_history(e["id"], "luminosity", 40)
            charts.append({"title": f"Luminosity — {e.get('refRoom', e['id'])}", "attr": "luminosity", "points": hist, "color": "#f59e0b"})
        elif e.get("type") == "TemperatureSensor":
            hist = await ql_history(e["id"], "temperature", 40)
            charts.append({"title": f"Temperature — {e.get('refRoom', e['id'])}", "attr": "temperature", "points": hist, "color": "#ef4444"})
        elif e.get("type") == "MotionSensor":
            hist = await ql_history(e["id"], "motion", 40)
            charts.append({"title": f"Motion — {e.get('refRoom', e['id'])}", "attr": "motion", "points": hist, "color": "#3b82f6"})
    return templates.TemplateResponse(
        "reports.html",
        {"request": request, "user": user, "charts": charts},
    )


@app.get("/api/entities")
async def api_entities(request: Request):
    if not current_user(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await orion_get_entities()


@app.get("/api/history/{entity_id}/{attr}")
async def api_history(request: Request, entity_id: str, attr: str):
    if not current_user(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await ql_history(entity_id, attr)
