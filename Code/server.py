import json
import asyncio
import uuid
import os
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeSerializer, BadSignature
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

# ── MongoDB ───────────────────────────────────────────────────────────────────

MONGODB_URL = os.getenv("MONGODB_URL", "")
if not MONGODB_URL:
    raise RuntimeError(
        "MONGODB_URL is not set. Add it to a .env file before starting."
    )

mongo_client = AsyncIOMotorClient(MONGODB_URL)
db = mongo_client.linkshare          # database name
devices_col = db.devices             # collection: devices
events_col  = db.share_events        # collection: share_events

# ── App ───────────────────────────────────────────────────────────────────────

SECRET_KEY    = os.getenv("SECRET_KEY",    "linkshare-dev-secret-change-in-production")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
serializer    = URLSafeSerializer(SECRET_KEY)
COOKIE_NAME   = "ls_session"
ADMIN_COOKIE  = "ls_admin"

app = FastAPI(title="LinkShare")

connected: dict[str, WebSocket] = {}   # device_id → active WebSocket


@app.on_event("startup")
async def on_startup():
    # Unique index on device name so duplicates are rejected at DB level
    await devices_col.create_index("name", unique=True)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_pw(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def get_session(request: Request) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        return serializer.loads(token)
    except BadSignature:
        return None


def require_auth(request: Request) -> dict:
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return session


def set_auth_cookie(response: JSONResponse, device_id: str) -> None:
    token = serializer.dumps({"device_id": device_id})
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")


def device_to_dict(doc: dict) -> dict:
    return {"id": doc["_id"], "name": doc["name"], "icon": doc["icon"]}


def is_admin(request: Request) -> bool:
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        return False
    try:
        return serializer.loads(token).get("admin") is True
    except BadSignature:
        return False


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")


app.mount("/public", StaticFiles(directory="public"), name="public")


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse(url="/public/login.html")


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    name     = str(form.get("name",     "")).strip()
    password = str(form.get("password", "")).strip()

    if not name or not password:
        return JSONResponse({"error": "Name and password required"}, status_code=400)

    doc = await devices_col.find_one({"name": name})
    if not doc or not verify_pw(password, doc["password_hash"]):
        return JSONResponse({"error": "Invalid name or password"}, status_code=401)

    response = JSONResponse({"ok": True, "device": device_to_dict(doc)})
    set_auth_cookie(response, doc["_id"])
    return response


@app.post("/register")
async def register(request: Request):
    form = await request.form()
    name     = str(form.get("name",     "")).strip()
    password = str(form.get("password", "")).strip()
    icon     = str(form.get("icon",     "💻")).strip()

    if not name or not password:
        return JSONResponse({"error": "Name and password required"}, status_code=400)
    if len(name) > 32:
        return JSONResponse({"error": "Name must be 32 characters or fewer"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"error": "Password must be at least 6 characters"}, status_code=400)

    existing = await devices_col.find_one({"name": name})
    if existing:
        return JSONResponse({"error": "Device name already taken"}, status_code=409)

    device_id = str(uuid.uuid4())
    new_doc = {
        "_id":           device_id,
        "name":          name,
        "password_hash": hash_pw(password),
        "icon":          icon,
        "created_at":    datetime.now(timezone.utc),
    }
    await devices_col.insert_one(new_doc)

    response = JSONResponse({"ok": True, "device": device_to_dict(new_doc)})
    set_auth_cookie(response, device_id)
    return response


@app.post("/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/dashboard")
async def dashboard(request: Request):
    if not get_session(request):
        return RedirectResponse(url="/public/login.html")
    return RedirectResponse(url="/public/dashboard.html")


@app.get("/api/me")
async def me(request: Request):
    session = require_auth(request)
    doc = await devices_col.find_one({"_id": session["device_id"]})
    if not doc:
        raise HTTPException(status_code=404)
    return device_to_dict(doc)


@app.get("/api/devices")
async def devices_list(request: Request):
    require_auth(request)
    online = set(connected.keys())
    docs = await devices_col.find({}).sort("created_at", 1).to_list(None)
    return [
        {"id": d["_id"], "name": d["name"], "icon": d["icon"], "online": d["_id"] in online}
        for d in docs
    ]


@app.get("/api/device-names")
async def device_names():
    docs = await devices_col.find({}).sort("created_at", 1).to_list(None)
    return [{"id": d["_id"], "name": d["name"], "icon": d["icon"]} for d in docs]


@app.get("/api/history")
async def get_history(request: Request):
    require_auth(request)
    # Fetch last 200 events newest-first, then reverse to return oldest-first
    cursor = events_col.find({}).sort("timestamp", -1).limit(200)
    docs = await cursor.to_list(None)
    docs.reverse()
    return [
        {
            "type":      "incoming_share",
            "from_id":   e["from_id"],
            "from_name": e["from_name"],
            "from_icon": e["from_icon"],
            "content":   e["content"],
            "target":    e["target"],
            "timestamp": e["timestamp"].isoformat(),
        }
        for e in docs
    ]


# ── Admin ────────────────────────────────────────────────────────────────────

ADMIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LinkShare — Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@800&display=swap" rel="stylesheet">
<style>
  :root{--bg:#070b10;--card:#0d1520;--border:#1c2d3f;--text:#c8d8e4;--dim:#4d6a7a;--accent:#00e87a;--red:#ff3355;--mono:'Space Mono',monospace;--display:'Syne',sans-serif;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{min-height:100vh;background:var(--bg);color:var(--text);font-family:var(--mono);padding:32px 20px;}
  .header{display:flex;align-items:center;gap:16px;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid var(--border);}
  .logo{font-family:var(--display);font-size:1.5rem;font-weight:800;color:var(--accent);text-shadow:0 0 20px rgba(0,232,122,0.4);}
  .badge{font-size:0.58rem;letter-spacing:0.22em;color:var(--red);background:rgba(255,51,85,0.1);border:1px solid rgba(255,51,85,0.3);border-radius:3px;padding:4px 10px;}
  .logout-btn{margin-left:auto;font-family:var(--mono);font-size:0.6rem;letter-spacing:0.18em;color:var(--dim);background:transparent;border:1px solid var(--border);border-radius:3px;padding:6px 14px;cursor:pointer;transition:all .18s;}
  .logout-btn:hover{color:var(--red);border-color:var(--red);}
  .section-title{font-size:0.6rem;letter-spacing:0.28em;color:var(--dim);margin-bottom:14px;}
  table{width:100%;border-collapse:collapse;max-width:760px;}
  th{font-size:0.58rem;letter-spacing:0.2em;color:var(--dim);text-align:left;padding:8px 12px;border-bottom:1px solid var(--border);}
  td{padding:10px 12px;border-bottom:1px solid rgba(28,45,63,0.5);font-size:0.78rem;vertical-align:middle;}
  tr:hover td{background:rgba(255,255,255,0.015);}
  .icon-cell{font-size:1.2rem;width:48px;}
  .name-cell{font-weight:700;}
  .id-cell{color:var(--dim);font-size:0.65rem;}
  .online-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#2a3a4a;}
  .online-dot.on{background:var(--accent);box-shadow:0 0 5px var(--accent);}
  .del-btn{font-family:var(--mono);font-size:0.6rem;letter-spacing:0.15em;color:var(--red);background:transparent;border:1px solid rgba(255,51,85,0.35);border-radius:3px;padding:5px 12px;cursor:pointer;transition:all .15s;}
  .del-btn:hover{background:rgba(255,51,85,0.1);border-color:var(--red);}
  .empty{color:var(--dim);font-size:0.7rem;letter-spacing:0.1em;padding:24px 0;}
  .toast{position:fixed;bottom:24px;right:24px;background:var(--card);border:1px solid var(--border);border-radius:4px;padding:12px 18px;font-size:0.7rem;letter-spacing:0.1em;opacity:0;transition:opacity .3s;pointer-events:none;}
  .toast.show{opacity:1;}
  .toast.ok{border-color:var(--accent);color:var(--accent);}
  .toast.err{border-color:var(--red);color:var(--red);}
</style>
</head>
<body>
<div class="header">
  <div class="logo">LINKSHARE</div>
  <div class="badge">ADMIN PANEL</div>
  <button class="logout-btn" onclick="adminLogout()">LOGOUT</button>
</div>
<div class="section-title">REGISTERED DEVICES</div>
<table id="device-table">
  <thead><tr><th></th><th>NAME</th><th>ID</th><th>STATUS</th><th></th></tr></thead>
  <tbody id="device-tbody"><tr><td colspan="5" class="empty">Loading...</td></tr></tbody>
</table>
<div class="toast" id="toast"></div>
<script>
  async function load(){
    const res = await fetch('/api/admin/devices');
    if(!res.ok){window.location.href='/admin/login';return;}
    const devices = await res.json();
    const tbody = document.getElementById('device-tbody');
    if(!devices.length){tbody.innerHTML='<tr><td colspan="5" class="empty">NO DEVICES REGISTERED</td></tr>';return;}
    tbody.innerHTML = devices.map(d=>`
      <tr id="row-${d.id}">
        <td class="icon-cell">${d.icon}</td>
        <td class="name-cell">${esc(d.name)}</td>
        <td class="id-cell">${d.id.slice(0,8)}…</td>
        <td><span class="online-dot ${d.online?'on':''}"></span> ${d.online?'ONLINE':'OFFLINE'}</td>
        <td><button class="del-btn" onclick="del('${d.id}','${esc(d.name)}')">DELETE</button></td>
      </tr>`).join('');
  }
  async function del(id,name){
    if(!confirm('Delete device "'+name+'"? This cannot be undone.'))return;
    const res = await fetch('/api/admin/device/'+id,{method:'DELETE'});
    const data = await res.json();
    if(res.ok){document.getElementById('row-'+id)?.remove();toast('Deleted '+name,'ok');}
    else{toast(data.error||'Failed','err');}
  }
  async function adminLogout(){
    await fetch('/admin/logout',{method:'POST'});
    window.location.href='/admin/login';
  }
  function toast(msg,type){
    const el=document.getElementById('toast');
    el.textContent=msg;el.className='toast '+type+' show';
    setTimeout(()=>el.classList.remove('show'),2800);
  }
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  load();
  setInterval(load, 8000);
</script>
</body>
</html>"""

ADMIN_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LinkShare — Admin Login</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@800&display=swap" rel="stylesheet">
<style>
  :root{--bg:#070b10;--card:#0d1520;--border:#1c2d3f;--text:#c8d8e4;--dim:#4d6a7a;--accent:#00e87a;--red:#ff3355;--mono:'Space Mono',monospace;--display:'Syne',sans-serif;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{min-height:100vh;background:var(--bg);color:var(--text);font-family:var(--mono);display:flex;align-items:center;justify-content:center;}
  .card{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:36px 32px;width:100%;max-width:380px;}
  .logo{font-family:var(--display);font-size:1.6rem;font-weight:800;color:var(--accent);text-align:center;margin-bottom:4px;text-shadow:0 0 20px rgba(0,232,122,0.4);}
  .sub{font-size:0.58rem;letter-spacing:0.28em;color:var(--dim);text-align:center;margin-bottom:28px;}
  label{display:block;font-size:0.58rem;letter-spacing:0.22em;color:var(--dim);margin-bottom:7px;}
  input{width:100%;background:rgba(0,0,0,0.45);border:1px solid var(--border);border-radius:3px;color:var(--text);font-family:var(--mono);font-size:0.82rem;padding:10px 13px;outline:none;margin-bottom:20px;transition:border-color .18s;}
  input:focus{border-color:var(--accent);}
  .err{font-size:0.65rem;color:var(--red);min-height:1.3em;margin-bottom:12px;}
  button{width:100%;background:transparent;border:1px solid var(--accent);border-radius:3px;color:var(--accent);font-family:var(--mono);font-size:0.72rem;font-weight:700;letter-spacing:0.24em;padding:12px;cursor:pointer;transition:all .18s;}
  button:hover{background:var(--accent);color:var(--bg);}
</style>
</head>
<body>
<div class="card">
  <div class="logo">LINKSHARE</div>
  <div class="sub">ADMIN ACCESS</div>
  <form id="form">
    <label>ADMIN PASSWORD</label>
    <input type="password" id="pass" placeholder="••••••••••" autofocus required>
    <div class="err" id="err"></div>
    <button type="submit">ENTER</button>
  </form>
</div>
<script>
  document.getElementById('form').addEventListener('submit',async(e)=>{
    e.preventDefault();
    const pass=document.getElementById('pass').value;
    const fd=new FormData();fd.append('password',pass);
    const res=await fetch('/admin/login',{method:'POST',body:fd});
    if(res.ok){window.location.href='/admin';}
    else{const d=await res.json();document.getElementById('err').textContent='⚠  '+(d.error||'Wrong password').toUpperCase();}
  });
</script>
</body>
</html>"""


@app.get("/admin/login")
async def admin_login_page():
    return HTMLResponse(ADMIN_LOGIN_PAGE)


@app.post("/admin/login")
async def admin_login(request: Request):
    if not ADMIN_PASSWORD:
        return JSONResponse({"error": "ADMIN_PASSWORD is not configured"}, status_code=503)
    form = await request.form()
    password = str(form.get("password", ""))
    if password != ADMIN_PASSWORD:
        return JSONResponse({"error": "Wrong password"}, status_code=401)
    token = serializer.dumps({"admin": True})
    response = JSONResponse({"ok": True})
    response.set_cookie(ADMIN_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/admin/logout")
async def admin_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(ADMIN_COOKIE)
    return response


@app.get("/admin")
async def admin_panel(request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/admin/login")
    return HTMLResponse(ADMIN_PAGE)


@app.get("/api/admin/devices")
async def admin_list_devices(request: Request):
    require_admin(request)
    online = set(connected.keys())
    docs = await devices_col.find({}).sort("created_at", 1).to_list(None)
    return [
        {
            "id":     d["_id"],
            "name":   d["name"],
            "icon":   d["icon"],
            "online": d["_id"] in online,
        }
        for d in docs
    ]


@app.delete("/api/admin/device/{device_id}")
async def admin_delete_device(device_id: str, request: Request):
    require_admin(request)
    doc = await devices_col.find_one({"_id": device_id})
    if not doc:
        return JSONResponse({"error": "Device not found"}, status_code=404)

    # Kick the device off WebSocket if it's connected
    if device_id in connected:
        try:
            await connected[device_id].close(code=4003, reason="Device deleted by admin")
        except Exception:
            pass
        connected.pop(device_id, None)

    await devices_col.delete_one({"_id": device_id})
    await events_col.delete_many({"from_id": device_id})

    await push_device_list()
    return JSONResponse({"ok": True, "deleted": doc["name"]})


# ── WebSocket ─────────────────────────────────────────────────────────────────

async def push_device_list():
    online = set(connected.keys())
    docs = await devices_col.find({}).sort("created_at", 1).to_list(None)
    payload = json.dumps({
        "type": "device_list",
        "devices": [
            {"id": d["_id"], "name": d["name"], "icon": d["icon"], "online": d["_id"] in online}
            for d in docs
        ],
    })
    dead = []
    for did, ws in list(connected.items()):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(did)
    for did in dead:
        connected.pop(did, None)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    token = websocket.cookies.get(COOKIE_NAME)
    if not token:
        await websocket.close(code=4001, reason="Missing session")
        return
    try:
        session = serializer.loads(token)
    except BadSignature:
        await websocket.close(code=4001, reason="Invalid session")
        return

    device_id = session.get("device_id")
    device_doc = await devices_col.find_one({"_id": device_id})
    if not device_doc:
        await websocket.close(code=4001, reason="Unknown device")
        return

    if device_id in connected:
        try:
            await connected[device_id].close(code=4002, reason="Replaced by new connection")
        except Exception:
            pass

    await websocket.accept()
    connected[device_id] = websocket
    await push_device_list()

    ping_task: Optional[asyncio.Task] = None

    async def keep_alive():
        while True:
            await asyncio.sleep(25)
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break

    ping_task = asyncio.create_task(keep_alive())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "share":
                content = str(msg.get("content", "")).strip()
                target  = str(msg.get("target",  "all"))
                if not content:
                    continue

                now = datetime.now(timezone.utc)
                event = {
                    "type":      "incoming_share",
                    "from_id":   device_doc["_id"],
                    "from_name": device_doc["name"],
                    "from_icon": device_doc["icon"],
                    "content":   content,
                    "target":    target,
                    "timestamp": now.isoformat(),
                }

                await events_col.insert_one({
                    "from_id":   device_doc["_id"],
                    "from_name": device_doc["name"],
                    "from_icon": device_doc["icon"],
                    "content":   content,
                    "target":    target,
                    "timestamp": now,
                })

                if target == "all":
                    recipients = [did for did in connected if did != device_id]
                else:
                    recipients = [target] if target in connected else []

                payload = json.dumps(event)
                dead = []
                for did in recipients:
                    if did in connected:
                        try:
                            await connected[did].send_text(payload)
                        except Exception:
                            dead.append(did)
                for did in dead:
                    connected.pop(did, None)

    except WebSocketDisconnect:
        pass
    finally:
        if ping_task:
            ping_task.cancel()
        if connected.get(device_id) is websocket:
            connected.pop(device_id, None)
        await push_device_list()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
