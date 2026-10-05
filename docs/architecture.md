# Two-Mac Architecture

## Mac 1 — 10.7.29.7
- Private DNS
- Test Client
- Backend B on port 3002

## Mac 2 — 10.7.3.153
- nginx Reverse Proxy
- TLS Termination
- Load Balancer
- Backend A on port 3001

## Request Flow

Client on Mac 1
→ DNS on Mac 1
→ app.cn-project.test resolves to Mac 2
→ nginx on Mac 2
→ Backend A on Mac 2:3001
or
→ Backend B on Mac 1:3002
