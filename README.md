# Private Network Service Platform

Computer Networks course project.

## Two-Mac Architecture

### Mac 1
- Private DNS Server
- Test Client
- Backend B on port 3002

### Mac 2
- nginx Reverse Proxy
- TLS Termination
- Load Balancer
- Backend A on port 3001

## Request Flow

Client
→ DNS
→ nginx Edge
→ Backend A / Backend B
