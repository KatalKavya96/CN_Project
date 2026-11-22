# Viva command menu — choose what the teacher asks to see

Current three-Mac deployment, 23 November 2026. Run each block on the named
person's Mac. Commands are for the real systems, not Newton Packet Tracer.

## Choose a demonstration

| Teacher asks to see… | Section |
| --- | --- |
| What each Mac does | [1. Explain the architecture](#1-explain-the-architecture) |
| IP addresses and connectivity | [2. LAN](#2-lan-addresses-and-connectivity) |
| Primary and backup DNS records | [3. Direct DNS](#3-query-both-dns-servers) |
| DNS settings used by applications | [4. System resolver](#4-check-the-system-resolver) |
| TCP, certificate verification and HTTPS | [5. HTTPS](#5-verified-https) |
| Requests distributed between A and B | [6. Load balancing](#6-load-balancing) |
| Cache headers and a 304 response | [7. HTTP caching](#7-http-caching-and-304) |
| One backend failing and recovering | [8. Backend A failure](#8-backend-a-failure-and-recovery) |
| Primary DNS failing | [9. Backup DNS](#9-primary-dns-failure--priyanshu-takes-over-resolution) |
| Direct backend access blocked | [10. Firewall](#10-backend-firewall-isolation) |
| Moving traffic to the standby edge | [11. DNS cutover](#11-ttl-and-standby-edge-cutover) |
| Both DNS services unavailable | [12. DNS outage](#12-both-active-dns-services-stopped) |
| Both backends unavailable | [13. HTTP 502](#13-both-backends-stopped--http-502) |
| Incorrect DNS configuration or record | [14. Wrong DNS](#14-wrong-client-dns-and-wrong-record) |
| Wrong port versus TLS failure | [15. TCP and TLS faults](#15-wrong-port-versus-tls-hostname-failure) |
| DNS/TCP/TLS packets | [16. Wireshark](#16-packet-flow-in-wireshark) |
| Diagnosis of an unknown fault | [17. Troubleshooting](#17-diagnose-an-unknown-fault) |
| Restoring the complete demo | [18. Restore](#18-restore-normal-state) |

**Operating rule:** Start in normal state. Perform one fault at a time. Restore
it before selecting another demonstration. Leave chargers connected, lids open,
the same Wi-Fi selected, and existing nginx serving sessions running.

## 0. One-time Terminal preparation

On all three Macs, in a separate Terminal tab, run and leave running:

```bash
caffeinate -dimsu
```

### Kavya — main tab

```bash
cd /Users/kavyakatal/Desktop/CN_Project
admin() { sudo -n /usr/local/sbin/cn-project-admin "$@"; }
CN_URL='https://app.cn-project.test:8443/api/status'
web() { /usr/bin/curl --noproxy '*' --connect-timeout 5 --max-time 30 "$@" "$CN_URL"; }
requests() {
  for i in 1 2 3 4 5 6; do
    echo "Request $i"
    web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Backend:|^X-Edge:/'
  done
}
```

### Ronit — main tab

```bash
cd /Users/ronitsingh/Desktop/CN_Project
admin() { sudo -n /usr/local/sbin/cn-project-admin "$@"; }
CN_URL='https://app.cn-project.test:8443/api/status'
web() { /usr/bin/curl --noproxy '*' --connect-timeout 5 --max-time 30 "$@" "$CN_URL"; }
requests() {
  for i in 1 2 3 4 5 6; do
    echo "Request $i"
    web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Backend:|^X-Edge:/'
  done
}
```

### Priyanshu — main tab

```bash
cd /Users/priyanshutomar/CN_Project
backup() { sudo -n /usr/local/sbin/cn-project-backup "$@"; }
```

Repeat shortcut definitions if you open a new main tab. `web` uses normal DNS
and default certificate trust. `requests` makes six requests and prints only
HTTP status, backend and edge. First use [section 18](#18-restore-normal-state)
to establish normal state; then start the demonstration you need.

## 1. Explain the architecture

| Person | Address | Real services |
| --- | --- | --- |
| Kavya | 10.7.26.228 | Primary DNS :53; Backend B :3002; standby nginx :8080/:8443; client |
| Ronit | 10.7.18.166 | Primary nginx :8080/:8443; TLS termination; Backend A :3001; client |
| Priyanshu | 10.7.26.237 | Backup DNS UDP/TCP :53 only |

Normal path:

```text
Client -- DNS question --> Kavya or Priyanshu
       <-- address 10.7.18.166
Client -- TCP + TLS + HTTP --> Ronit's nginx :8443
                               |-- A on Ronit, 127.0.0.1:3001
                               +-- B on Kavya, 10.7.26.228:3002
```

**Say:** “DNS finds the edge address. nginx receives HTTPS and selects a backend.
A backend generates the response. One physical Mac can run several services.”
Priyanshu handles DNS, not the website traffic. Ronit's retired DNS stays stopped.

## 2. LAN addresses and connectivity

Kavya:

```bash
hostname
ipconfig getifaddr en0
ifconfig en0
route -n get default
ping -c 3 10.7.18.166
```

Ronit:

```bash
hostname
ipconfig getifaddr en0
ping -c 3 10.7.26.228
```

Priyanshu:

```bash
hostname
ipconfig getifaddr en0
ping -c 3 10.7.26.228
```

**Expect:** Table addresses, subnet mask 255.255.224.0 (/19), gateway 10.7.0.1,
and successful ping replies. Recheck addresses if Wi-Fi changes; editing lab.env
alone does not update installed root-owned DNS settings.

**Say:** “ICMP replies prove these IP paths work. They do not establish that DNS,
the web port, certificate verification or the application works.”

## 3. Query both DNS servers

Kavya:

```bash
dig @10.7.26.228 app.cn-project.test
dig @10.7.26.228 api.cn-project.test +short
```

Priyanshu:

```bash
dig @10.7.26.237 app.cn-project.test
dig @10.7.26.237 api.cn-project.test +short
```

**Expect:** NOERROR; A record 10.7.18.166; TTL 30 in full answers.

**Say:** “Both DNS servers agree on the edge address. @ selects a server
explicitly; this test alone does not prove operating-system fallback.”

If asked about UDP versus TCP, either client can run:

```bash
dig @10.7.26.237 app.cn-project.test
dig @10.7.26.237 app.cn-project.test +tcp
```

Both should answer. DNS supports both transports.

## 4. Check the system resolver

Kavya and Ronit, each:

```bash
cat /etc/resolver/cn-project.test
dscacheutil -q host -a name app.cn-project.test
```

**Expect:** Nameservers 10.7.26.228 and 10.7.26.237; system answer 10.7.18.166.

**Say:** “Applications use the macOS resolver. This domain-specific file lists
our two DNS servers. A result may be cached; we will flush caches for failover.”

## 5. Verified HTTPS

Kavya and Ronit, one after the other:

```bash
web -v
```

**Expect:** Connection to 10.7.18.166:8443, certificate verification success,
HTTP 200, X-Edge: mac2 and X-Backend: A or B.

**Say:** “The client resolves the name, establishes TCP, verifies TLS, and sends
HTTP. nginx terminates TLS and forwards to a backend. We did not use -k.”

If asked about listening ports, each client Mac can show:

```bash
lsof -nP -iTCP:8443 -sTCP:LISTEN
```

## 6. Load balancing

Kavya:

```bash
requests
```

Ronit:

```bash
tail -n 8 .runtime/nginx-access.log
```

**Expect:** All 200, edge mac2, both A and B. Concurrent requests can affect
visible alternating order; pause other requests while showing the loop.

**Say:** “DNS returns one edge address. nginx uses round robin across two
upstreams. X-Backend shows which application answered; X-Edge shows the proxy.”

## 7. HTTP caching and 304

Kavya:

```bash
web -sS -I
for i in 1 2 3 4 5 6; do
  web -sS -D - -o /dev/null -H 'If-None-Match: "A-v1"' |
    tr -d '\r' | awk '/^HTTP|^ETag:|^Cache-Control:|^X-Backend:/'
done
```

**Expect:** Cache-Control: max-age=60; ETags; A returns 304 for its matching
validator, while B returns 200 for the different representation.

**Say:** “A matching ETag produces 304 without resending the body. HTTP freshness
of 60 seconds is separate from the DNS TTL of 30 seconds.” This tests headers
and conditional validation; curl is not automatically caching these responses.

## 8. Backend A failure and recovery

Ronit:

```bash
/usr/bin/python3 phase2/services.py stop a
```

Kavya:

```bash
requests
```

**Expect:** 200, mac2, B only. The first request can take longer.

**Say:** “Only Backend A stopped. nginx detects upstream failure through real
requests and retries B. These are passive checks, not continuous active pings.”

**Restore — Ronit:**

```bash
/usr/bin/python3 phase2/services.py start a
sleep 6
```

Kavya runs `requests` again: expect A/B. max_fails=1 and fail_timeout=5s govern
the passive failure interval; a later request can try the recovered backend.

## 9. Primary DNS failure — Priyanshu takes over resolution

Kavya:

```bash
admin dns-stop
```

Ronit:

```bash
dig @10.7.26.228 app.cn-project.test +time=1 +tries=1
```

**Expect:** This explicit primary query fails. Next, Kavya and Ronit each run:

```bash
admin cache-flush
dscacheutil -q host -a name app.cn-project.test
web -sS -i
```

Priyanshu:

```bash
backup dns-status
```

**Expect:** Both clients resolve 10.7.18.166 and receive 200/mac2. Backup logs
show client queries. Allow several seconds for fallback.

**Say:** “After clearing cached answers, both clients resolve through backup
DNS. The website stays on Ronit's edge; only the DNS provider changed.”

**Restore — Kavya:**

```bash
admin dns-start
admin cache-flush
```

Ronit:

```bash
admin cache-flush
```

## 10. Backend firewall isolation

Kavya and Ronit, each:

```bash
admin firewall-on
```

Kavya:

```bash
/usr/bin/curl --noproxy '*' --connect-timeout 3 --max-time 4 \
  -i http://10.7.18.166:3001/api/status
web -sS -i
admin firewall-status
```

Ronit:

```bash
/usr/bin/curl --noproxy '*' --max-time 5 -i http://127.0.0.1:3001/api/status
/usr/bin/curl --noproxy '*' --max-time 5 -i http://10.7.26.228:3002/api/status
admin firewall-status
```

**Expect:** Kavya's direct A request times out; HTTPS and the edge's permitted
paths succeed. Inspect project rule counters.

**Say:** “A dedicated PF anchor restricts backend access while keeping the
primary edge's allowed paths. We preserve the main ruleset.”

**Restore immediately — Kavya and Ronit, each:**

```bash
admin firewall-off
```

Remove these rules before standby cutover, because Kavya's edge needs LAN access
to A. The saved proof uses the original two-client scope; an independent
third-source rejection test for B was not added with the DNS migration.

## 11. TTL and standby edge cutover

Start with project firewall rules off on both original Macs. Kavya and Ronit:

```bash
admin cache-flush
web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
```

Expect mac2. Kavya:

```bash
admin dns-standby
```

Priyanshu immediately follows:

```bash
backup dns-standby
```

Kavya, without flushing:

```bash
dig @10.7.26.228 app.cn-project.test
dig @10.7.26.237 app.cn-project.test
dscacheutil -q host -a name app.cn-project.test
web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
```

Both server answers should be 10.7.26.228. A cached request may still use mac2.
If it already changed, report that; do not claim a stale answer was observed.

Ronit becomes the fresh client:

```bash
admin cache-flush
web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
```

Expect mac1. Kavya observes natural adoption:

```bash
sleep 35
for i in 1 2 3 4 5; do
  date
  dscacheutil -q host -a name app.cn-project.test
  web -sS -D - -o /dev/null | tr -d '\r' | awk '/^HTTP|^X-Edge:/'
  sleep 2
done
```

**Say:** “Both DNS servers advertise the standby. Clients adopt the new answer
as caches refresh. A manual flush makes adoption immediate. Existing TCP
connections do not move just because DNS changes.” macOS may need another
refresh cycle after nominal TTL expiry; describe what actually happened.

**Restore — Kavya:**

```bash
admin dns-primary
```

Priyanshu:

```bash
backup dns-primary
```

Then Kavya and Ronit each run `admin cache-flush` and `requests`: expect mac2/A/B.
This is manual cutover; automatic edge failover would also need health monitoring
and traffic steering.

## 12. Both active DNS services stopped

Only during this coordinated test. Leave nginx and backends running. Ronit's
retired DNS must remain stopped; do not start it to prepare this experiment.

Kavya:

```bash
admin dns-stop
```

Priyanshu:

```bash
backup dns-stop
```

Kavya and Ronit, each:

```bash
admin cache-flush
web -sS -i
/usr/bin/curl --noproxy '*' --connect-timeout 5 --max-time 15 \
  -i http://10.7.18.166:8080/api/status
/usr/bin/curl --noproxy '*' --connect-timeout 5 --max-time 15 \
  --resolve app.cn-project.test:8443:10.7.18.166 -i "$CN_URL"
```

**Expect:** Fresh normal-name request fails resolution/times out. Direct HTTP
and explicit-destination verified HTTPS succeed.

**Say:** “The DNS outage prevents fresh name resolution, but the edge and
application remain healthy. --resolve bypasses DNS while retaining the proper
hostname for TLS. It cannot prove DNS works.”

**Restore — Kavya:** `admin dns-start`. **Priyanshu:** `backup dns-start`.
Then both client Macs run `admin cache-flush` and `web -sS -i`: expect 200.

## 13. Both backends stopped — HTTP 502

Kavya:

```bash
/usr/bin/python3 phase2/services.py stop b
```

Ronit:

```bash
/usr/bin/python3 phase2/services.py stop a
```

Kavya and Ronit:

```bash
web -v
```

**Expect:** TLS verification still succeeds, but HTTP is 502 Bad Gateway.

**Say:** “DNS, TCP and TLS reached nginx successfully. nginx cannot obtain a
response from either backend, so it returns 502.”

**Restore — Kavya:**

```bash
/usr/bin/python3 phase2/services.py start b
```

Ronit:

```bash
/usr/bin/python3 phase2/services.py start a
```

Wait six seconds. Both client Macs run `requests`: expect 200/mac2/A/B.

## 14. Wrong client DNS and wrong record

### Wrong client resolver — independent short demonstration

Kavya or Ronit, from that Mac's repository:

```bash
/usr/bin/python3 phase2/wrong-dns-client.py
web -sS -i
```

**Expect:** The temporary resolver cannot resolve the name and is stopped by
the script; normal system HTTPS still works.

**Say:** “This is a deliberately misconfigured temporary client resolver. It
does not change macOS global DNS preferences. It illustrates lookup failure.”

### Wrong real DNS destination, with restoration

Start from normal state. Kavya stops only her standby edge:

```bash
/opt/homebrew/bin/nginx -s quit -c "$PWD/.runtime/nginx.conf"
sleep 2
admin dns-standby
```

Priyanshu:

```bash
backup dns-standby
```

Both client Macs:

```bash
admin cache-flush
dscacheutil -q host -a name app.cn-project.test
web -v
```

**Expect:** DNS resolves to 10.7.26.228, but the HTTPS connection fails because
we deliberately stopped that address's edge. This is not a failed DNS lookup.

**Say:** “DNS returned a syntactically valid answer that directs the request
to a destination without the required service. Correct resolution and a
working destination are separate checks.”

**Restore — Kavya:**

```bash
admin dns-primary
/opt/homebrew/bin/nginx -c "$PWD/.runtime/nginx.conf"
```

Priyanshu:

```bash
backup dns-primary
```

Both clients run `admin cache-flush` and `requests`: expect mac2/A/B. Verify
Kavya's standby listener is restored with `lsof -nP -iTCP:8443 -sTCP:LISTEN`.

## 15. Wrong port versus TLS hostname failure

Kavya or Ronit:

```bash
/usr/bin/curl --noproxy '*' --connect-timeout 3 --max-time 5 \
  -v https://app.cn-project.test:8444/api/status
```

**Expect:** Connection failure; no project listener on 8444.

Then:

```bash
/usr/bin/curl --noproxy '*' --connect-timeout 5 --max-time 15 \
  --resolve wrong.cn-project.test:8443:10.7.18.166 \
  -v https://wrong.cn-project.test:8443/api/status
```

**Expect:** TLS hostname verification fails (curl error 60).

Finally:

```bash
web -v
```

**Expect:** Correct request succeeds. No restoration is needed; these requests
change no server configuration.

**Say:** “The first fault is at the TCP destination port. The second reaches
the server, but its certificate does not cover the requested hostname.”

## 16. Packet flow in Wireshark

Kavya opens the fresh real failure/cutover capture:

```bash
open -a Wireshark evidence/rehearsal/2026-11-23T143307/phase2/dns-failover-cutover.pcap
```

Use display filters individually:

```text
dns
tcp.port == 8443
tls.handshake.type == 1
tls.handshake.type == 2
tls.record.content_type == 23
```

Choose one TCP connection and filter on its tcp.stream number to find SYN,
SYN-ACK and ACK. Point out source/destination IPs and ports, sequence and ACK
numbers, and ClientHello SNI where present.

**Say:** “This is a saved capture from our actual test. DNS supplies the IP;
TCP provides ordered reliable delivery; TLS negotiates encryption. TLS 1.3
encrypts later handshake messages and application data. curl shows HTTP after
decryption.” Do not claim every TLS message or the HTTP body is readable here.

## 17. Diagnose an unknown fault

Kavya or Ronit:

```bash
bash phase2/diagnose.sh
```

Ronit:

```bash
tail -n 15 .runtime/nginx-error.log
tail -n 15 .runtime/nginx-access.log
/usr/bin/python3 phase2/services.py status a
```

Kavya:

```bash
/usr/bin/python3 phase2/services.py status b
```

Priyanshu:

```bash
backup dns-status
```

| Observation | Investigate |
| --- | --- |
| Hostname cannot resolve | DNS server, record, resolver configuration/cache |
| Connection refused | Listening process, destination port, explicit rejection |
| Timeout | Availability, LAN path, silent filtering |
| Certificate verification error | CA trust, hostname/SAN, validity |
| HTTP 502 | Upstream address, backend process, backend port |
| --resolve works but normal name fails | Difference in DNS/client resolution |

**Say:** “We isolate the failing layer before changing configuration.” Do not
use -k to claim successful TLS, or restart all services to hide an unknown cause.

## 18. Restore normal state

Kavya:

```bash
admin dns-primary
admin dns-start
admin firewall-off
/usr/bin/python3 phase2/services.py start b
```

Priyanshu:

```bash
backup dns-primary
backup dns-start
```

Ronit:

```bash
admin firewall-off
/usr/bin/python3 phase2/services.py start a
```

Ronit's old DNS must stay stopped. Do not run `admin dns-start` there. Its stop
helper returns exit 1 when already stopped; that alone does not mean a fault.

If section 14 deliberately stopped Kavya's standby, start it using its restore
command. Otherwise inspect listeners first and leave healthy nginx instances up:

```bash
lsof -nP -iTCP:8443 -sTCP:LISTEN
```

Only if Kavya has no listener:

```bash
/opt/homebrew/bin/nginx -c "$PWD/.runtime/nginx.conf"
```

Only if Ronit has no listener, he opens a separate tab and leaves this running:

```bash
cd /Users/ronitsingh/Desktop/CN_Project
/usr/bin/python3 phase2/start-edge.py
```

Do not close a healthy serving Terminal/SSH session. Then Kavya and Ronit each:

```bash
admin cache-flush
sleep 6
requests
```

**Final expected state:** 200, mac2, both A and B. Both client resolver files
still list 10.7.26.228 and 10.7.26.237. Primary/backup DNS records agree.

## Evidence and rehearsal notes

- [Latest real-system rehearsal and results](../evidence/rehearsal/2026-11-23T143307/README.md)
- [Current three-Mac migration evidence](../evidence/phase-2/mac3-dns/README.md)
- [Architecture](architecture.md) and [viva questions](viva.md)

To run the three additional Phase 1 failures as one coordinated automated
experiment, Kavya can use `python3 phase2/phase1-failures.py`. For learning and
live explanation, use the individual sections above. Never run that script or
the complete final-tests suite simultaneously with manual injected faults.

Do not run setup_repo.sh, historical repair scripts, reinstall existing helpers,
replace certificates, close lids, switch Wi-Fi/VPN or reboot during the viva.
