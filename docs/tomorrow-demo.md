# Tomorrow's Two-Mac Demo: Commands, Roles, and Spoken Explanation

Follow this order. Read the explanation, run the command, point to the expected
output, then move on. Plan roughly 20-25 minutes plus faculty questions.
The live faculty challenge and viva are performed by you, not by a script.

## Roles and current addresses

| Person | Machine | Current IP | Responsibility |
| --- | --- | --- | --- |
| Kavya | Mac 1 | 10.7.26.228 | Present topology, run client requests, control primary DNS and Backend B, show Wireshark and standby edge |
| Ronit | Mac 2 | 10.7.18.166 | Explain nginx/TLS, control Backend A and backup DNS, show upstream logs and firewall evidence |

Both Macs use `en0`, mask `255.255.224.0` (/19), and gateway `10.7.0.1`.
Normal edge is Mac 2. Standby edge is Mac 1. Both listen on HTTPS 8443.

## Before the evaluator arrives

Connect to the same Wi-Fi, plug in power, and leave lids open. On both Macs,
run `caffeinate -dimsu` in a separate tab and leave that tab running.

Kavya, main Terminal tab:

```bash
cd /Users/kavyakatal/Desktop/CN_Project
git status --short
git log -1 --oneline
ipconfig getifaddr en0
```

Ronit, main Terminal tab:

```bash
cd /Users/ronitsingh/Desktop/CN_Project
git status --short
git log -1 --oneline
ipconfig getifaddr en0
```

The addresses must still match the table above. If either has changed, fix
the lab configuration before presenting. Changing `phase2/lab.env` alone
does not update the installed root-owned DNS configs and resolver files.
Never run `setup_repo.sh` or reinstall the admin helper over this deployment.

In BOTH main Terminal tabs, define these shortcuts. Repeat these definitions
if you open another tab for demo commands:

```bash
CN_URL='https://app.cn-project.test:8443/api/status'
admin() { sudo -n /usr/local/sbin/cn-project-admin "$@"; }
web() { /usr/bin/curl --noproxy '*' --connect-timeout 5 --max-time 30 "$@" "$CN_URL"; }
```

`web` uses normal DNS and default certificate trust. It adds neither `-k`,
`--cacert`, nor `--resolve`. All ordinary requests below use this function.

On BOTH main tabs, restore the normal starting state:

```bash
admin dns-primary
admin dns-start
admin firewall-off
admin cache-flush
```

Kavya:

```bash
/usr/bin/python3 phase2/services.py start b
lsof -nP -iTCP:8443 -sTCP:LISTEN
```

If Kavya's port 8443 has NO listener, start standby nginx:

```bash
/opt/homebrew/bin/nginx -c "$PWD/.runtime/nginx.conf"
```

Ronit:

```bash
/usr/bin/python3 phase2/services.py start a
lsof -nP -iTCP:8443 -sTCP:LISTEN
```

The existing primary edge runs in foreground mode inside a persistent SSH
session. Keep that session alive. If it is already listening and A/B works,
leave it running. If no listener exists, Ronit opens a separate Terminal tab,
runs the following and leaves that tab running without pressing Control+C:

```bash
cd /Users/ronitsingh/Desktop/CN_Project
/usr/bin/python3 phase2/start-edge.py
```

If the primary listener exists but repeatedly returns only A because nginx
cannot reach B, use the recovery instructions at the end of this guide.
Do not start a second nginx instance on an occupied port.

On BOTH main tabs, final warm-up:

```bash
web -sS -i
```

Expect HTTP 200 and `X-Edge: mac2`. Then verify A/B with step 5 below.

## 1. Topology and service inventory

Kavya opens `docs/architecture.md`, scrolling to the Phase 2 deployment.

Kavya says:

> We combined the four logical roles across two Macs. My Mac hosts primary
> DNS, Backend B, and the standby edge. Ronit's Mac hosts primary nginx,
> Backend A, and backup DNS. Both machines also act as clients.

Ronit says:

> A normal request follows DNS, TCP, TLS, HTTP, nginx, then a backend response.
> On my edge, Backend A is 127.0.0.1:3001 and Backend B is 10.7.26.228:3002.
> The client uses a domain name and does not choose a backend.

## 2. Show the LAN and connectivity

Kavya:

```bash
ifconfig en0
route -n get default
ping -c 3 10.7.18.166
```

Ronit:

```bash
ifconfig en0
route -n get default
ping -c 3 10.7.26.228
```

Point out `inet`, `netmask`, `ether`, `interface`, and `gateway`.
Expect successful replies in both directions.

Kavya says:

> Both Macs share the private LAN. The /19 subnet mask determines the network
> and host portions. Ping demonstrates IP reachability; it does not prove
> that DNS, TLS, or an application port is working.

## 3. Show private DNS

Kavya:

```bash
dig @10.7.26.228 app.cn-project.test
dig @10.7.26.228 api.cn-project.test +short
scutil --dns
dscacheutil -q host -a name app.cn-project.test
```

Ronit:

```bash
dig @10.7.18.166 app.cn-project.test
dscacheutil -q host -a name app.cn-project.test
```

Expect both names to resolve to `10.7.18.166`. In the full dig answer, show
TTL `30`. In `scutil --dns`, show the `cn-project.test` resolver listing BOTH
`10.7.26.228` and `10.7.18.166`.

Kavya says:

> Our private names use .test to avoid macOS .local/mDNS conflicts. DNS maps
> the name to the edge IP; it does not establish the connection. Direct dig
> queries a chosen server; dscacheutil and curl use the macOS resolver.

## 4. Show plain trusted HTTPS

Kavya:

```bash
web -v
```

Ronit repeats:

```bash
web -v
```

Point to the resolved address, connection to port 8443, certificate hostname
match, `SSL certificate verify ok.`, and `HTTP/1.1 200 OK`.

Ronit says:

> nginx terminates TLS at the edge. The certificate contains our project
> names as SANs and is signed by our local CA, trusted on both client Macs.
> These requests use default trust without bypassing verification. Our
> standby has its own private key and a certificate from the same CA.

## 5. Show load balancing

Kavya runs:

```bash
for i in 1 2 3 4 5 6; do
  echo "Request $i"
  web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Backend:|^X-Edge:/'
done
```

Expect both A and B, with `X-Edge: mac2`. Other concurrent client requests
can affect the exact visible alternating order, so avoid refreshing elsewhere.

Ronit, optionally showing the latest actual upstreams:

```bash
tail -n 8 .runtime/nginx-access.log
```

Ronit says:

> nginx uses round robin across two upstreams. X-Backend identifies the
> selected backend and X-Edge identifies the edge. These logs show actual
> upstream addresses, response statuses, and timings.

## 6. Show DNS, TCP and TLS in Wireshark

Kavya opens the saved capture:

```bash
open -a Wireshark evidence/phase-2/final/dns-failover-cutover.pcap
```

Use these DISPLAY filters one at a time in Wireshark's filter bar:

```text
dns.qry.name == "app.cn-project.test"
tcp.port == 8443
tls.handshake.type == 1
tls.handshake.type == 2
tls.record.content_type == 23
```

For one connection, select a packet and use Follow -> TCP Stream or filter
on its `tcp.stream` number. Point to SYN, SYN-ACK, ACK and the socket ports.

Kavya says:

> The DNS request and reply show the name-to-IP lookup. This TCP stream
> begins with SYN, SYN-ACK and ACK; the client has an ephemeral source port
> and the edge destination is 8443. TCP provides ordered reliable delivery
> using sequence numbers, acknowledgements and retransmission.

Ronit says:

> ClientHello carries SNI app.cn-project.test. ServerHello negotiates TLS.
> With TLS 1.3, later handshake messages including the certificate are
> encrypted on the wire. Application data is encrypted too; curl shows
> HTTP headers after decryption. Not every TLS message is visible as plaintext.

## 7. Show caching and conditional 304

Kavya:

```bash
web -sS -I
for i in 1 2 3 4; do
  web -sS -D - -o /dev/null -H 'If-None-Match: "A-v1"' |
    tr -d '\r' | awk '/^HTTP|^ETag:|^Cache-Control:|^X-Backend:/'
done
```

Show `Cache-Control: max-age=60`, ETag, and at least one `304 Not Modified`.
A B response may return 200 for the A ETag; that is expected.

Kavya says:

> A fresh cached response may be reused without contacting the server.
> A conditional request sends a validator; a matching ETag produces 304
> without a response body. Our A and B representations have different ETags,
> so an A validator can return 200 if the request reaches B.

## 8. Stop Backend A and demonstrate recovery

Ronit:

```bash
/usr/bin/python3 phase2/services.py stop a
```

Kavya repeats the six-request loop from step 5. Expect all responses HTTP
200 with `X-Backend: B`. Ronit can repeat the loop on his main tab too.

Ronit says:

> Only Backend A's process is stopped. DNS and the TLS edge remain up.
> nginx passively detects the failed upstream and retries B. We use a
> two-second connect timeout, max_fails=1 and fail_timeout=5 seconds.

Ronit restores A:

```bash
/usr/bin/python3 phase2/services.py start a
sleep 6
```

Kavya repeats step 5. Expect A and B again.

Ronit says:

> After the failure interval, requests can try the recovered backend again.
> Stopping this entire Mac would also stop the edge and backup DNS: that is
> fate sharing. A standby plus manual DNS cutover provides controlled recovery,
> but automatic edge HA additionally needs health monitoring and traffic steering.

## 9A. Backup DNS failover

Kavya stops primary DNS, then flushes her client cache:

```bash
admin dns-stop
admin cache-flush
dscacheutil -q host -a name app.cn-project.test
web -sS -i
```

Ronit proves the primary no longer answers, then uses normal OS resolution:

```bash
dig @10.7.26.228 app.cn-project.test +time=1 +tries=1
admin cache-flush
dscacheutil -q host -a name app.cn-project.test
web -sS -i
admin dns-status
```

The explicit primary query should fail. Both OS lookups and HTTPS should
succeed; backup logs should show queries. Allow a few seconds for fallback.

Kavya says:

> We flushed cached answers so this is real fallback, not just reuse of
> an old name. Primary DNS no longer answers, yet both clients resolve
> through backup DNS. DNS failure and backend failure affect different layers.

Restore before the next test. Kavya:

```bash
admin dns-start
admin cache-flush
```

Ronit:

```bash
admin cache-flush
```

## 9B. Backend firewall isolation and rollback

On BOTH main tabs:

```bash
admin firewall-on
```

Kavya tests forbidden direct Backend A access:

```bash
/usr/bin/curl --noproxy '*' --connect-timeout 3 --max-time 4 -i http://10.7.18.166:3001/api/status
web -sS -i
```

The direct request should time out, while HTTPS still returns 200.

Ronit tests permitted edge paths:

```bash
/usr/bin/curl --noproxy '*' --max-time 5 -i http://127.0.0.1:3001/api/status
/usr/bin/curl --noproxy '*' --max-time 5 -i http://10.7.26.228:3002/api/status
admin firewall-status
```

Kavya also shows `admin firewall-status` on her Mac.

Ronit says:

> These stateful PF rules allow the edge's source IP to reach backend ports
> and block other LAN sources. The client cannot reach A directly but can
> still use HTTPS through nginx. We use a dedicated anchor and preserve the
> main ruleset. With only two Macs, we cannot independently test an unrelated
> third client's rejection by B: the other Mac is also the allowed edge.

On BOTH Macs, roll back now, before the standby needs remote Backend A:

```bash
admin firewall-off
```

Ronit says:

> We removed only the project rules and released only our own PF enable
> reference. The original firewall configuration is preserved. The kernel's
> No ALTQ support notice concerns optional queueing, not failure of these rules.

## 9C. TTL and DNS-based edge cutover

First prime BOTH OS caches while records point at Mac 2. On BOTH Macs:

```bash
admin cache-flush
web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
```

Expect `X-Edge: mac2`. Then, on BOTH Macs, change each DNS server's record:

```bash
admin dns-standby
```

Do not flush Kavya's cache yet. Kavya shows live server data and her cached
client's destination:

```bash
dig @10.7.26.228 app.cn-project.test
dig @10.7.18.166 app.cn-project.test
dscacheutil -q host -a name app.cn-project.test
web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
```

Direct DNS should now answer `10.7.26.228`, TTL 30. An existing cached client
may still reach mac2. If the cache already refreshed, report what happened
and show the saved old/new evidence; do not claim a stale answer was observed.

Ronit becomes the fresh client by flushing only his cache:

```bash
admin cache-flush
dscacheutil -q host -a name app.cn-project.test
web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
```

Expect `X-Edge: mac1`. Kavya says:

> Both DNS servers now advertise the standby. My cached client can briefly
> remain on the old edge, while Ronit's flushed client moves immediately.
> Both edges keep serving during the transition. TTL governs DNS caching;
> it does not terminate an existing TCP connection.

Kavya observes expiry without flushing:

```bash
sleep 35
for i in 1 2 3 4 5; do
  date
  dscacheutil -q host -a name app.cn-project.test
  web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
  sleep 2
done
```

Expect adoption of Mac 1. In our saved run, macOS returned an old answer on
the first post-TTL lookup while refreshing, then the new answer on the next
poll at about 39 seconds. Describe measured behavior, not an exact promise.

Restore DNS on BOTH Macs:

```bash
admin dns-primary
```

Then flush BOTH client caches and prove immediate return to the primary:

```bash
admin cache-flush
web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
```

Expect `X-Edge: mac2`. Ronit says:

> We restored consistent records on both DNS servers and flushed clients.
> Manual flush gives immediate adoption; normal clients otherwise age their
> caches independently. This is DNS-based cutover, not automatic edge failover.

## 10. Faculty-injected troubleshooting

Ask the evaluator to inject the fault. Kavya leads the first diagnosis;
Ronit checks edge/backend logs. Swap if faculty requests.

Either Mac, from the repo root:

```bash
bash phase2/diagnose.sh
```

Kavya says:

> I will isolate the layer before changing configuration. First I check
> the resolver and answer, then TCP connectivity, certificate verification,
> HTTP status, and finally the upstream/backend.

Useful manual commands on Kavya's Mac:

```bash
scutil --dns
dig @10.7.26.228 app.cn-project.test
dig @10.7.18.166 app.cn-project.test
dscacheutil -q host -a name app.cn-project.test
nc -vz -G 3 10.7.18.166 8443
web -v
/usr/bin/curl --noproxy '*' --resolve app.cn-project.test:8443:10.7.18.166 -v "$CN_URL"
```

Ronit:

```bash
tail -n 15 .runtime/nginx-error.log
tail -n 15 .runtime/nginx-access.log
/usr/bin/python3 phase2/services.py status a
/usr/bin/curl --noproxy '*' --max-time 5 -i http://127.0.0.1:3001/api/status
/usr/bin/curl --noproxy '*' --max-time 5 -i http://10.7.26.228:3002/api/status
```

Interpret the result aloud:

| Observation | Likely layer and next check |
| --- | --- |
| Cannot resolve hostname | DNS server, records, scoped resolver, cache |
| Connection refused | TCP port/listener, explicit rejection |
| Connection timed out | Host availability, silent filter, LAN path |
| Certificate verification error | CA trust, SAN/hostname, expiry, wrong certificate |
| HTTP 502 | TLS edge reached; inspect upstream addresses, ports and backend processes |
| Direct edge via `--resolve` works, normal name fails | DNS/client resolution differs; TLS and application can still work |

Do not use `-k`, restart everything, or change multiple layers at once.

## 11. Individual viva and closing

Both students should explain their own and the other Mac's components.
Review `docs/viva.md`. Be ready for TTL versus TCP lifetime, ports and socket
pairs, certificate trust and SNI, DNS versus app failure, passive checks versus
active probes, firewall state, rollback, and shared host/router failure points.

For cloud comparisons: private DNS resembles a managed DNS service; nginx
plays the reverse-proxy/load-balancer role; the backends resemble application
instances. Our HTTP cache-header demonstration does not implement a CDN.
DNS/HTTP are application protocols, TCP/UDP transport, IP network, and the
LAN link is Wi-Fi/Ethernet. TLS sits above TCP; OSI placement is conceptual.
HTTP/2 is optional if supported and configured; HTTP/3 and email protocols
are explanation topics. SMTP sends mail; IMAP/POP3 retrieve/access it.

Kavya closes:

> We demonstrated the full request path, trusted HTTPS, two backends,
> DNS redundancy, caching and cutover, backend recovery, isolation and rollback,
> and diagnosis by layer. Our evidence records both observations and recovery.

## Optional: show the other Phase 1 failures if asked

The fixed 11-step sequence already covers one backend stopped. Saved logs for
the three additional demonstrations are under
`evidence/phase-1/failures-2026-11-22/`.

Kavya can rerun all three on both Macs with one coordinated script:

```bash
/usr/bin/python3 phase2/phase1-failures.py
```

Keep Ronit's primary edge foreground session running. This script temporarily
misconfigures a client-scoped resolver on each Mac, then changes real DNS
records with the standby stopped, then stops both backends and observes 502.
It restores DNS, standby nginx and both backends. It requires the existing
SSH key and installed admin helpers. Do not simultaneously run manual faults.

Say:

> Wrong client DNS fails lookup while IP connectivity remains. That test
> uses an explicitly configured temporary client resolver; it does not change
> macOS global DNS settings. With a wrong record, DNS succeeds but directs the
> client to a host without the edge service. With both backends stopped,
> DNS and verified TLS still work but nginx returns 502.

For a separate wrong-port example, Kavya runs:

```bash
/usr/bin/curl --noproxy '*' --connect-timeout 3 --max-time 5 -v https://app.cn-project.test:8444/api/status
```

Say: "The hostname and host are valid, but no service listens on port 8444."

## Recovery and final normal state

If interrupted during any failure, first undo the specific fault. Then run
these commands on BOTH main tabs:

```bash
admin dns-primary
admin dns-start
admin firewall-off
admin cache-flush
```

Kavya:

```bash
/usr/bin/python3 phase2/services.py start b
```

Ronit:

```bash
/usr/bin/python3 phase2/services.py start a
```

Wait six seconds, then repeat step 5 on both Macs. Expect HTTP 200, mac2,
and A/B. If the standby was deliberately stopped and is not listening, Kavya
starts it with `/opt/homebrew/bin/nginx -c "$PWD/.runtime/nginx.conf"`.

If Ronit's nginx must be relaunched because of upstream routing errors,
Ronit runs the following in a separate Terminal tab and leaves it open:

```bash
cd /Users/ronitsingh/Desktop/CN_Project
/opt/homebrew/bin/nginx -s quit -c "$PWD/.runtime/nginx.conf"
sleep 2
/usr/bin/python3 phase2/start-edge.py
```

Only do this targeted restart when needed. Verify A/B again afterward.
Do not overwrite certificates, rerun historical repair scripts, or reinstall
dependencies during the live presentation.
