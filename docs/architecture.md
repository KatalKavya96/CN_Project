# Phase 1 two-Mac architecture

| Mac | LAN IP | Role and ports |
| --- | --- | --- |
| Mac 1 — Kavya | `10.7.25.0` | Primary DNS `:53`, client, Backend B `:3002` |
| Mac 2 — Ronit | `10.7.13.163` | nginx HTTP `:8080` / HTTPS `:8443`, TLS termination, round-robin load balancer, Backend A `:3001` |

Both Macs share a reachable private LAN. The client on Mac 1 queries its primary DNS service for `app.cn-project.test` or `api.cn-project.test`; both names resolve to `10.7.13.163` (Mac 2). Mac 2 can also query Mac 1 DNS.

```text
Client (Mac 1)
  ├─ DNS query → Mac 1 :53 → app/api.cn-project.test = 10.7.13.163
  └─ HTTPS → Mac 2 nginx :8443 (TLS terminates here)
                    ├─ Backend A, Mac 2 127.0.0.1:3001
                    └─ Backend B, Mac 1 10.7.25.0:3002
```

nginx also listens on `:8080` for HTTP testing. The HTTPS client knows only the edge name and port. nginx forwards HTTP requests to the two backends in round-robin order and returns their JSON, `X-Backend`, cache headers, and ETags. The response returns over the same TCP/TLS connection to the client.
