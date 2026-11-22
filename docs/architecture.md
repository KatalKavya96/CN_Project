# Phase 1 Architecture

The Phase 1 addresses below are the October checkpoint. For the current
November Phase 2 deployment, see the additional section at the end and
`phase2/lab.env`.

## Purpose

This Phase 1 project demonstrates the full path of a private web request across the local lab network:

```text
DNS -> TCP -> TLS -> HTTP -> nginx load balancing -> backend response
```

The client resolves a private test domain, opens a TCP connection to the nginx edge, verifies the TLS certificate, sends an HTTP request through the encrypted TLS session, and receives a response from one of two backend servers selected by nginx round-robin load balancing.

## Two-Mac Deployment

| Machine | IP | Interface | Roles | Services |
| --- | --- | --- | --- | --- |
| Mac 1 - Kavya | `10.7.25.0` | `en0` | Primary DNS, client/test, Backend B | DNS `:53`, Backend B `:3002` |
| Mac 2 - Ronit | `10.7.13.163` | `en0` | nginx edge, TLS termination, load balancer, Backend A | Backend A `:3001`, HTTP `:8080`, HTTPS `:8443` |

These IP addresses are DHCP lab addresses. Recheck both Macs with `ifconfig en0` before the demo and update the local configuration if the lab assigns different addresses.

## Private DNS

The private DNS service runs on Mac 1 and resolves both project hostnames to the nginx edge on Mac 2:

```text
app.cn-project.test -> 10.7.13.163
api.cn-project.test -> 10.7.13.163
```

The project uses the `.test` top-level domain because it is reserved for testing and documentation. This avoids conflicts with `.local`, which is commonly used by mDNS/Bonjour on macOS and can be intercepted by the operating system before the query reaches dnsmasq.

## Request Flow Diagram

```text
Client
  |
  | DNS UDP/53
  v
Mac 1 dnsmasq
  |
  | app.cn-project.test = 10.7.13.163
  v
Mac 2 nginx :8443
  |
  | TLS termination
  | round-robin
  +----------------+
  |                |
Backend A         Backend B
127.0.0.1:3001   10.7.25.0:3002
```

## Protocol Mapping

| Layer or step | Protocol / behavior | Phase 1 role |
| --- | --- | --- |
| DNS lookup | DNS over UDP `:53` | The client asks Mac 1 DNS for `app.cn-project.test` or `api.cn-project.test` and receives `10.7.13.163`. |
| TCP connection | TCP three-way handshake | The client opens a reliable ordered connection to Mac 2 on port `8443`. |
| TLS session | TLS handshake and certificate verification | nginx presents a certificate for the project hostnames and terminates TLS at the edge. |
| HTTP request | HTTP/1.1 | The client sends `GET /` or `GET /api/status` inside the encrypted TLS session. |
| Load balancing | nginx upstream round-robin | nginx alternates requests between Backend A and Backend B. |
| Response path | Backend response through nginx, TLS, and TCP | The selected backend response returns to nginx, then back to the client over the existing encrypted connection. |

## Backend Behavior

Both Backend A and Backend B provide the same Phase 1 HTTP behavior:

- `GET /`
- `GET /api/status`
- `HEAD` support
- `X-Backend` response header
- `Cache-Control: max-age=60`
- `ETag`
- `304 Not Modified` for matching conditional requests

Backend A runs on Mac 2 at `127.0.0.1:3001`. Backend B runs on Mac 1 at `10.7.25.0:3002`.

## TLS Trust Model

nginx terminates TLS on Mac 2 at port `8443`. The server certificate includes subject alternative names for:

```text
app.cn-project.test
api.cn-project.test
```

A local certificate authority signs the server certificate. Clients trust the public CA certificate, then verify the server certificate during the TLS handshake. Private keys and generated certificates are intentionally not committed to the repository.

Final proof must use normal certificate verification. Do not use `curl -k` for final HTTPS evidence because `-k` disables certificate verification.

## Failure Behavior

The selected D3 failure test is an application/backend-layer failure:

```text
healthy -> A/B
Backend A stopped -> B only
Backend A restarted -> A/B restored
```

During this test, DNS, TCP, TLS, and nginx remain operational. The demonstrated failure is that one upstream backend becomes unavailable while nginx continues routing successful requests to the remaining healthy backend. After Backend A restarts, round-robin behavior is restored.

## Packet Evidence

Saved Phase 1 evidence is under [`evidence/phase-1/`](../evidence/phase-1/). It includes proof for:

- DNS query and response
- TCP `SYN`, `SYN-ACK`, and `ACK`
- client ephemeral port
- destination port `8443`
- TLS `ClientHello`
- SNI `app.cn-project.test`
- TLS `ServerHello`
- encrypted TLS Application Data

## Phase 2 Deployment: 22 November 2026

| Machine | Current address | Interface | Services |
| --- | --- | --- | --- |
| Mac 1 - Kavya | `10.7.26.228/19` | `en0` | Primary DNS :53, Backend B :3002, standby nginx :8080/:8443, client |
| Mac 2 - Ronit | `10.7.18.166/19` | `en0` | Backup DNS :53, Backend A :3001, primary nginx :8080/:8443, client |

Both machines have subnet mask `255.255.224.0`. These DHCP addresses must be
rechecked on the demonstration network. Both clients list both DNS servers
in their scoped resolver for `cn-project.test`.
The observed gateway is `10.7.0.1`; full interface inventories are saved in
`evidence/phase-2/baseline/mac1-final-inventory.txt` and `mac2-final-inventory.txt`.

```text
                       DNS: primary Mac 1 / backup Mac 2
                                      |
Client -- TCP/TLS :8443 --> primary edge Mac 2
                                      |-- local Backend A 127.0.0.1:3001
                                      +-- remote Backend B 10.7.26.228:3002

DNS cutover: app/api -> Mac 1 (TTL 30 seconds)
Client -- TCP/TLS :8443 --> standby edge Mac 1
                                      |-- remote Backend A 10.7.18.166:3001
                                      +-- local Backend B 127.0.0.1:3002
```

Each edge uses a different private key and a certificate signed by the same
local CA for both project names. The CA private key stays on Mac 2.
`X-Edge: mac1` or `mac2` identifies the serving edge; `X-Backend` identifies
the backend. Logs include upstream address, status, and response time.

nginx uses passive failure detection (`max_fails=1`, `fail_timeout=5s`), a
two-second upstream connect timeout, and retries failed connections on the
other backend. These are request-driven passive checks, not scheduled probes.
After the failure interval, a real request can try a recovered backend again.

DNS records live in a root-owned hosts file reloaded with SIGHUP. Both resolvers
must receive the same cutover choice. A direct `dig` query tests current server
data; OS/application requests test cached behavior. DNS TTL does not close an
existing TCP connection, so migration tests use new curl processes.

The firewall demonstration allows only the primary edge's LAN address to reach
backend ports over `en0`. Rules run in a dedicated PF anchor with a reversible
enable reference. Remove the primary-only isolation policy before testing the
standby edge, which needs LAN access to Backend A. Loopback traffic and clients
sharing an edge's source address cannot be distinguished by these IP rules.

A stopped Backend A process on Mac 2 models an application failure; stopping
the whole Mac also loses primary nginx and backup DNS. This role coupling is
fate sharing. Standby nginx plus manual DNS cutover reduces recovery work but
is not automatic host failover. Automatic edge recovery also needs health
monitoring and a traffic steering mechanism. The Wi-Fi/router remains a shared
failure point, and two DNS servers still share the same LAN.
