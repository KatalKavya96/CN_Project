# Computer Networks Course Project — Running Project Record

## Project
**Private Network Service Platform**

**Core principle:** The application stays simple; the network is the project.

This file is the single running record for the project. It should be updated after every meaningful step with:
- configuration/state,
- observed output,
- interpretation,
- evidence to save,
- dependencies,
- next action.

---

# 1. Target Architecture

The intended four-machine topology is:

```text
Client / DNS
Mac 1
10.7.29.7
   |
   | DNS resolution
   v
Edge / Reverse Proxy / Load Balancer
Mac 2
10.7.3.153
   |
   +-------------------+
   |                   |
   v                   v
Backend A           Backend B
Mac 3               Mac 4
10.7.13.163         TBD
:3001               :3002
```

Planned role assignment:

| Machine | Hostname | Primary Role | Planned Service(s) |
|---|---|---|---|
| Mac 1 | Kavyas-MacBook-Pro.local | Private DNS + Test Client | dnsmasq, dig/nslookup, curl/browser |
| Mac 2 | Priyanshus-MacBook-Pro-6.local | Edge / Reverse Proxy / Load Balancer | nginx, TLS, load balancing |
| Mac 3 | Ronits-MacBook-Pro.local | Backend A | Simple HTTP/REST app on port 3001 |
| Mac 4 | TBD | Backend B + Test Client | Simple HTTP/REST app on port 3002 |

---

# 2. Current Phase

## Phase 1 — Build & Observe

Current sub-stage:

**Establish and verify the private LAN before installing role-specific services.**

Reason:

All later protocols and services depend on basic IP reachability. If machines cannot exchange IP packets, DNS, TCP, TLS, HTTP, nginx, and backend communication cannot work reliably.

Current mental stack:

```text
Application       not configured yet
HTTP              not configured yet
TLS               not configured yet
TCP services       not configured yet
IP reachability    being verified now
Local LAN          being verified now
```

---

# 3. Network Inventory

## Mac 1 — DNS + Client

Observed:

```text
Hostname:  Kavyas-MacBook-Pro.local
IPv4:      10.7.29.7
Gateway:   10.7.0.1
Interface: en0
```

Commands used:

```bash
hostname
ipconfig getifaddr en0
route -n get default
```

Interpretation:

- `en0` is the active interface being used for the current connection.
- `10.7.29.7` is Mac 1's current private IPv4 address.
- `10.7.0.1` is the default gateway.
- This machine will later host the private DNS resolver and also act as a test client.

---

## Mac 2 — Edge / nginx / Load Balancer

Observed:

```text
Hostname:  Priyanshus-MacBook-Pro-6.local
IPv4:      10.7.3.153
Gateway:   10.7.0.1
Interface: en0
```

Commands used:

```bash
hostname
ipconfig getifaddr en0
route -n get default
```

Interpretation:

- Mac 2 is reachable on `10.7.3.153`.
- It shares the same default gateway as Mac 1.
- This machine will later become the single public/private service entry point for clients.
- nginx will eventually receive HTTPS traffic and forward requests to Backend A or Backend B.

---

## Mac 3 — Backend A

Observed:

```text
Hostname:  Ronits-MacBook-Pro.local
IPv4:      10.7.13.163
Gateway:   10.7.0.1
Interface: en0
```

Commands used:

```bash
hostname
ipconfig getifaddr en0
route -n get default
```

Interpretation:

- Mac 3 is reachable on `10.7.13.163`.
- It shares the same default gateway as Mac 1 and Mac 2.
- This machine will later run Backend A on TCP port `3001`.

---

## Mac 4 — Backend B + Client

Status: **Not identified yet**

Required next inventory:

```bash
hostname
ipconfig getifaddr en0
route -n get default
```

Planned role:

- Backend B on port `3002`
- Secondary test client

---

# 4. Connectivity Tests and Observations

## Test 1 — Mac 1 → Mac 2

Command run on Mac 1:

```bash
ping 10.7.3.153
```

Observed result:

```text
8 packets transmitted
8 packets received
0.0% packet loss
round-trip min/avg/max/stddev =
13.746/39.639/94.620/26.616 ms
```

Conclusion:

**PASS**

Mac 1 can reach Mac 2 over IP.

Meaning:

```text
Mac 1
10.7.29.7
   |
   | ICMP Echo Request
   v
Mac 2
10.7.3.153
   |
   | ICMP Echo Reply
   v
Mac 1
```

This proves basic IP-layer reachability from the future DNS/client machine to the future edge machine.

---

## Test 2 — Mac 2 → Mac 1

Command run on Mac 2:

```bash
ping 10.7.29.7
```

Observed result:

```text
12 packets transmitted
12 packets received
0.0% packet loss
round-trip min/avg/max/stddev =
7.781/51.900/200.404/53.753 ms
```

Conclusion:

**PASS**

Mac 2 can reach Mac 1 over IP.

Combined result:

```text
Mac 1 <------> Mac 2
      two-way IP connectivity confirmed
```

Why this matters:

Later:
- Mac 1 will resolve the private domain,
- the client will connect to Mac 2,
- Mac 2 will send responses back to clients.

Two-way reachability between these machines is therefore foundational.

---

## Test 3 — Mac 1 → Mac 3

Command run on Mac 1:

```bash
ping 10.7.13.163
```

Observed result:

```text
8 packets transmitted
8 packets received
0.0% packet loss
round-trip min/avg/max/stddev =
30.272/190.731/1081.559/337.529 ms
```

Additional observation:

The first ICMP exchange was unusually slow:

```text
~1081 ms
```

Subsequent responses were much faster.

Conclusion:

**PASS**

Mac 1 can reach Mac 3 over IP.

Interpretation:

- The high first-response latency should be noted but is not currently treated as a failure.
- The important result at this stage is that there was `0.0% packet loss`.
- Mac 3 is reachable from the future DNS/client machine.

---

## Test 4 — Mac 2 → Mac 3

Status: **Pending**

This is an especially important path because the final application flow will be:

```text
Client
  |
  v
Mac 2 / nginx
  |
  v
Mac 3 / Backend A :3001
```

Required command on Mac 2:

```bash
ping 10.7.13.163
```

Expected purpose:

Verify that the future edge/load-balancer machine can reach the future Backend A machine before any HTTP service is installed.

---

# 5. Current Proven Network Map

```text
                    Current LAN

          confirmed              confirmed
Mac 1 <-----------------------> Mac 2
10.7.29.7                      10.7.3.153
DNS + Client                   Edge / nginx
   |
   | confirmed
   v
Mac 3
10.7.13.163
Backend A

Mac 2 → Mac 3     pending
Mac 4             pending identification
```

Important observation:

The hosts currently have addresses:

```text
Mac 1: 10.7.29.7
Mac 2: 10.7.3.153
Mac 3: 10.7.13.163
```

and all show:

```text
Default gateway: 10.7.0.1
Interface: en0
```

Their third IPv4 octets differ, so we should not infer the exact subnet structure until the subnet mask/prefix is recorded. However, direct IP communication has already been proven for the tested pairs.

---

# 6. Why We Are Testing in This Order

We are building from lower-level networking upward.

```text
1. LAN / IP reachability
        ↓
2. Backend services
        ↓
3. Edge / nginx reverse proxy
        ↓
4. Private DNS
        ↓
5. HTTPS / TLS
        ↓
6. HTTP caching
        ↓
7. Wireshark packet evidence
        ↓
8. Phase 2 resilience and failure recovery
```

This order helps isolate problems.

Example:

If nginx cannot reach Backend A later, but `ping` from Mac 2 to Mac 3 is known to work, then the problem is likely above basic IP reachability—possibly the backend process, TCP port, firewall, or nginx configuration.

This is the core troubleshooting mindset for the whole project:

```text
DNS?
  ↓
IP/TCP?
  ↓
TLS?
  ↓
HTTP/Application?
```

---

# 7. Evidence to Preserve

For every significant stage, preserve evidence immediately.

Current evidence worth keeping:

- Mac 1 hostname/IP/gateway/interface output
- Mac 2 hostname/IP/gateway/interface output
- Mac 3 hostname/IP/gateway/interface output
- Mac 1 → Mac 2 ping result
- Mac 2 → Mac 1 ping result
- Mac 1 → Mac 3 ping result

Later evidence folders should include:

```text
evidence/
├── phase-1/
│   ├── lan/
│   ├── dns/
│   ├── backend/
│   ├── nginx/
│   ├── tls/
│   ├── caching/
│   └── wireshark/
└── phase-2/
    ├── dns-failover/
    ├── ttl/
    ├── firewall/
    ├── backend-failover/
    ├── edge-migration/
    └── troubleshooting/
```

---

# 8. Next Action

Do **not** install nginx, dnsmasq, or backend applications yet.

Next:

1. Run from Mac 2:

```bash
ping 10.7.13.163
```

2. Record the result here.

3. Identify Mac 4 with:

```bash
hostname
ipconfig getifaddr en0
route -n get default
```

4. Complete the necessary LAN reachability matrix.

Only after the LAN foundation is validated should Backend A and Backend B be started.

---

# 9. Running Decision / Observation Log

| Step | Observation | Result | Meaning |
|---|---|---|---|
| Mac 1 identified | `10.7.29.7`, gateway `10.7.0.1`, `en0` | Recorded | Future DNS + client machine |
| Mac 2 identified | `10.7.3.153`, gateway `10.7.0.1`, `en0` | Recorded | Future nginx edge |
| Mac 3 identified | `10.7.13.163`, gateway `10.7.0.1`, `en0` | Recorded | Future Backend A |
| Mac 1 → Mac 2 ping | 8/8 received | PASS | Client/DNS machine can reach edge |
| Mac 2 → Mac 1 ping | 12/12 received | PASS | Edge can reach client/DNS machine |
| Mac 1 → Mac 3 ping | 8/8 received | PASS | Client/DNS machine can reach Backend A host |
| Mac 2 → Mac 3 ping | Pending | — | Next critical edge-to-backend test |
| Mac 4 identification | Pending | — | Needed to complete topology |

---

_Last updated: 30 September 2026_
