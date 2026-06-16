# Gerald Cloud Migration Plan

## Goal
Move `gerald_bridge.py` from Matt's local PC to a VPS or cloud function so that:
- Gerald is reachable when Matt is not on his home LAN (commuting, travel)
- The Flutter app connects over the internet via HTTPS
- Push notifications work even when the bridge PC is off

## Architecture (Target)

```
[Gerald Flutter App]
        │
        │ HTTPS (port 443)
        ▼
[Cloud VPS / Railway / Fly.io]
  ├─ gerald_bridge.py (FastAPI, uvicorn)
  ├─ nginx reverse proxy (SSL termination)
  ├─ FCM notification sender
  └─ Webhook relay to local PC (optional)
        │
        │ Webhook / SSH tunnel (optional: for local claude.cmd)
        ▼
[Matt's Local PC]
  └─ claude.cmd (Claude Code CLI)
```

## Phases

### Phase 1 — Containerise (Week 1)
- [x] Create `Dockerfile` (FastAPI + uvicorn)
- [x] Create `docker-compose.yml` (service + optional nginx)
- [ ] Test `docker build` and `docker run` locally
- [ ] Confirm all endpoints work in container

### Phase 2 — Cloud Deploy (Week 2)
- [ ] Choose host: Railway (simplest), Fly.io (free tier), or DigitalOcean Droplet
- [ ] Push Docker image or deploy via Railway CLI
- [ ] Point domain / subdomain: `gerald.mattberry.dev` (example)
- [ ] Enable HTTPS (Let's Encrypt via nginx or host-provided)

### Phase 3 — Secure the API (Week 2-3)
- [ ] Add Bearer token auth to all `/` endpoints in `gerald_bridge.py`
- [ ] Store token in Flutter `shared_preferences` (Settings → API Token)
- [ ] Rotate token via Settings screen

### Phase 4 — Local AI Bridge (Week 3)
Two options:
**Option A — Cloud-only Claude API (no local PC):**
- Use Anthropic API directly from VPS (openai-style SDK)
- No local PC needed; billed per token

**Option B — Relay to local PC (keep claude.cmd):**
- VPS receives prompt → webhook to local PC ngrok tunnel
- Local PC runs claude.cmd → result POSTed back to VPS
- VPS returns result to app

Recommendation: **Option A** for reliability; **Option B** for cost.

### Phase 5 — FCM Push Notifications (Week 4)
- [ ] Add Firebase project + service account to VPS
- [ ] Replace `register_device` stub with real FCM `send_message`
- [ ] Flutter: FCM token registration on app start
- [ ] Notify Matt when task completes (app backgrounded)

## Environment Variables (cloud_config.example.json)
See `cloud_config.example.json` for the required env vars.

## Cost Estimate
| Host | Monthly | Notes |
|------|---------|-------|
| Railway | ~$5 | 500h free/month |
| Fly.io | ~$0-3 | 3 shared VMs free |
| DigitalOcean | ~$6 | 1GB Droplet |
| Render | ~$0-7 | Free tier available |

Recommended: **Railway** for zero-devops startup.
