# CN Project — Private Network Service Platform

## Two-Mac Deployment

### Mac 1
- IP: 10.7.29.7
- DNS
- Client
- Backend B :3002

### Mac 2
- IP: 10.7.3.153
- nginx Edge
- Backend A :3001
- TLS
- Load Balancer

## Flow

Client
→ DNS
→ nginx Edge
→ Backend A / Backend B

## Core Tests

```bash
./tests/test-backends.sh
./tests/test-load-balancing.sh
./tests/test-dns.sh
./tests/test-cache.sh
```
