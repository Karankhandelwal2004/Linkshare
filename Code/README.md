# LinkShare

> Real-time link & text sharing across all your devices — no cables, no cloud clipboard, no limits.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat&logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=flat&logo=mongodb&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-Real--time-FF6B35?style=flat)

---

## What is LinkShare?

LinkShare is a self-hosted, real-time link and text sharing app built for people who constantly move URLs, snippets, and notes between their own devices (phone ↔ laptop ↔ desktop ↔ tablet).

Every registered device sees every other device live. Click a device card, paste a URL or text, hit send — the other device gets a full-screen popup with a sound alert and a one-click copy button.

No third-party services. No browser extensions. Just open the URL and go.

---

## Features

- **Real-time presence** — see which devices are online/offline instantly via WebSocket
- **Direct or broadcast** — send to one specific device or blast to all at once
- **Persistent history** — last 200 shared items survive server restarts (stored in MongoDB)
- **URL detection** — links render as clickable anchors in history and popups
- **Sound alert** — ascending chime fires on every incoming share
- **Auto-reconnect** — WebSocket reconnects automatically if the connection drops
- **Admin panel** — password-protected page to view and delete any registered device
- **Self-registration** — any device can register with a name, icon, and password; no hardcoded list
- **Dark aesthetic** — Space Mono + Syne fonts, animated grid background, crypto terminal vibe

---

## Screenshots

| Login / Register | Dashboard | Incoming Share Popup | Admin Panel |
|---|---|---|---|
| Device signup with icon picker | Live device grid + send form + signal log | Full-screen alert with copy button | Manage all registered devices |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · uvicorn |
| Real-time | WebSockets (native FastAPI) |
| Database | MongoDB Atlas (via Motor async driver) |
| Auth | itsdangerous signed cookies · bcrypt |
| Frontend | Vanilla HTML / CSS / JS — no framework, no build step |
| Fonts | Google Fonts (Space Mono + Syne) |
| Deploy | Railway / Render / Fly.io (Procfile included) |

---

## Quick Start (Local)

**1. Clone and install**
```bash
git clone https://github.com/Karankhandelwal2004/Linkshare.git
cd Linkshare
pip install -r requirements.txt
```

**2. Create your `.env` file**
```bash
cp .env.example .env
```
Then edit `.env`:
```env
MONGODB_URL=mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/
SECRET_KEY=any-long-random-string-here
ADMIN_PASSWORD=your-admin-password
```

**3. Run**
```bash
uvicorn server:app --host 0.0.0.0 --port 3000
```

Open **http://localhost:3000** in your browser, click **REGISTER**, and you're in.  
Open the same URL on another device on your network — register a second device and watch them appear in each other's grid.

---

## Deploy to Railway (Recommended — Free Tier)

1. Fork / push this repo to your GitHub account

2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub** → select this repo

3. In the Railway dashboard go to **Variables** and add:

   | Key | Value |
   |-----|-------|
   | `MONGODB_URL` | Your MongoDB Atlas connection string |
   | `SECRET_KEY` | Any long random string |
   | `ADMIN_PASSWORD` | A strong password for the admin panel |

4. Railway auto-detects the `Procfile` and deploys. You get a public `https://` URL in ~60 seconds. WebSocket upgrades to `wss://` automatically.

---

## Deploy to Render

1. **New Web Service** → connect your GitHub repo
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. Add the same three environment variables as above

---

## MongoDB Atlas Setup

1. Create a free cluster at [cloud.mongodb.com](https://cloud.mongodb.com)
2. **Database Access** → Add a user with read/write permissions
3. **Network Access** → Add `0.0.0.0/0` (required for cloud hosting)
4. **Connect** → **Drivers** → copy the `mongodb+srv://...` connection string

---

## Admin Panel

Navigate to `/admin` on your deployed URL.

- Login with your `ADMIN_PASSWORD`
- View all registered devices and their online status (auto-refreshes every 8 seconds)
- Delete any device — immediately closes their WebSocket connection and removes their share history

---

## Project Structure

```
Linkshare/
├── server.py           # FastAPI app — auth, REST API, WebSocket, admin routes
├── requirements.txt    # Python dependencies
├── Procfile            # For Railway / Render deployment
├── .env.example        # Environment variable template
├── public/
│   ├── login.html      # Login + Register page (tab toggle, icon picker)
│   └── dashboard.html  # Main interface — device grid, send form, signal log, popup
└── README.md
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | — | Redirect to login |
| `POST` | `/login` | — | Authenticate with name + password |
| `POST` | `/register` | — | Create new device account |
| `POST` | `/logout` | cookie | Clear session |
| `GET` | `/api/me` | cookie | Current device info |
| `GET` | `/api/devices` | cookie | All devices + online status |
| `GET` | `/api/history` | cookie | Last 200 share events |
| `WS` | `/ws` | cookie | Real-time channel |
| `GET` | `/admin` | admin cookie | Admin panel UI |
| `POST` | `/admin/login` | — | Admin authentication |
| `GET` | `/api/admin/devices` | admin cookie | All devices (admin view) |
| `DELETE` | `/api/admin/device/{id}` | admin cookie | Delete a device |

### WebSocket message format

**Send (client → server)**
```json
{ "type": "share", "content": "https://example.com", "target": "all" }
```
`target` is either `"all"` or a specific device UUID.

**Receive (server → client)**
```json
{ "type": "incoming_share", "from_id": "...", "from_name": "Nexus Alpha",
  "from_icon": "💻", "content": "https://example.com", "target": "all",
  "timestamp": "2025-05-25T10:30:00Z" }
```
```json
{ "type": "device_list", "devices": [ { "id": "...", "name": "...", "icon": "...", "online": true } ] }
```

---

## Security Notes

- `.env` is in `.gitignore` — never commit it
- Passwords are hashed with **bcrypt** (cost factor 12) — never stored in plaintext
- Session cookies are **HttpOnly** and signed with `itsdangerous` — tamper-proof
- Set `ADMIN_PASSWORD` to something strong before going public
- For production: restrict MongoDB Network Access to your server's IP instead of `0.0.0.0/0`

---

## License

MIT — do whatever you want with it.
