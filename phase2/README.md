# Phase 2 operating commands

Both Macs use the addresses in `lab.env`. Current network: Mac 1
`10.7.26.228/19`, Mac 2 `10.7.18.166/19`, interface `en0`.
Run commands from the repository root. Never run `setup_repo.sh` over this checkout.

## Generated configurations and certificates

Run `bash phase2/render.sh mac1` on Kavya's Mac and
`bash phase2/render.sh mac2` on Ronit's Mac. Outputs are ignored under `.runtime/`.
Each edge requires `.runtime/server.crt`, `.runtime/server.key`, and
`.runtime/ca.crt`. Mac 1 has a separate private key and a server certificate
signed by the existing CA on Mac 2. The CA private key stays on Mac 2.
Check nginx with `/opt/homebrew/bin/nginx -t -c "$PWD/.runtime/nginx.conf"`.
For Mac 1, start it with `/opt/homebrew/bin/nginx -c "$PWD/.runtime/nginx.conf"`.
For Mac 2, the tested working launch is `python3 phase2/start-edge.py` kept
running in a local terminal or a persistent authenticated SSH session. Detached
daemon launches on Mac 2 produced upstream EHOSTUNREACH; foreground launch
within a live SSH session passed. Do not close that session during the demo.

## Limited administrator access

Run `bash phase2/install-admin.sh mac1` or `mac2` once, entering the local
administrator password. The installer creates a root-owned helper at
`/usr/local/sbin/cn-project-admin`, fixed root-owned config under
`/private/var/db/cn-project`, and an exact-action sudoers rule for the local user.
It refuses to overwrite an existing installation.
The installed DNS addresses are fixed at install time. If DHCP changes,
editing `lab.env` and rendering nginx alone is insufficient; update the
root-owned DNS/resolver configuration with administrator access too.

The admin DNS service uses `/private/var/db/cn-project/dnsmasq.conf`;
it does not use `.runtime/dnsmasq.conf`. Do not run both DNS instances.
The installer also configures both project DNS addresses in
`/etc/resolver/cn-project.test` and saves the previous resolver file.

```bash
sudo -n /usr/local/sbin/cn-project-admin dns-start
sudo -n /usr/local/sbin/cn-project-admin dns-stop
sudo -n /usr/local/sbin/cn-project-admin dns-status
sudo -n /usr/local/sbin/cn-project-admin dns-primary
sudo -n /usr/local/sbin/cn-project-admin dns-standby
sudo -n /usr/local/sbin/cn-project-admin cache-flush
sudo -n /usr/local/sbin/cn-project-admin firewall-on
sudo -n /usr/local/sbin/cn-project-admin firewall-status
sudo -n /usr/local/sbin/cn-project-admin firewall-off
```

`dns-primary` points both names at Mac 2; `dns-standby` points them at Mac 1.
Apply the same choice on both DNS servers. The helper updates a hosts file
and sends SIGHUP to its own dnsmasq, so it does not restart DNS for record changes.
It never accepts arbitrary shell commands, paths, IPs, or process IDs.

## Evidence and troubleshooting

```bash
python3 phase2/probe.py --count 8 --expect both --out evidence/phase-2/baseline/os-resolver.txt
python3 phase2/probe.py --edge 10.7.18.166 --expect both --out evidence/phase-2/baseline/primary-edge.txt
bash phase2/diagnose.sh
```

The probe uses verified HTTPS with the public CA. `--edge` uses curl `--resolve`
to bypass DNS; it cannot prove DNS behavior. Omitting it uses the OS resolver.
`X-Edge` distinguishes the two edges, and `X-Backend` distinguishes the backends.
`dig @server` tests DNS directly; `dscacheutil` and curl test the macOS resolver.

Run `python3 phase2/final-tests.py` on Mac 1 for the complete two-Mac live suite.
It saves commands, exit codes and packet captures and restores services after
each controlled failure. To repeat only OS cutover with a new evidence folder:

```bash
python3 phase2/final-tests.py --only cutover --out-dir evidence/phase-2/cutover-demo
```

The tested macOS cache can return an old answer on the first post-TTL lookup
while starting a refresh. The suite polls a bounded refresh window and records
the actual answers. A flushed client moves immediately. See the acceptance
summary rather than interpreting the initial exact-timing failure as a final
failure. Both Macs now pass default trust after the approved Mac 1 user-keychain
CA installation; `--cacert` remains a valid portable verification option.

## Firewall stage and rollback

The root-owned PF rules apply only to the backend port on `en0`, allowing Mac 2
and blocking other remote sources. They use the existing `com.apple/*` wildcard
anchor through `com.apple/cn-project`; no main ruleset is replaced.
The helper takes and releases its own PF enable reference, preserving other
users of PF. `firewall-off` removes only the project rules and reference.

Run isolation before migration, then turn the project firewall off on both Macs.
Mac 1 as standby edge needs LAN access to Backend A, which the primary-only
isolation policy deliberately blocks. Loopback connections do not prove LAN
isolation. With two Macs, show Mac 1 blocked from Mac 2 port 3001, Mac 2 nginx
using local A and remote B, and rule counters. An independent third client
is needed to test rejection by Mac 1 port 3002 without sharing an edge IP.

## Isolated client-cache TTL and migration test

On Mac 1, `python3 phase2/ttl-cutover.py` measures the countdown using a temporary
dnsmasq client cache on 127.0.0.1:1053 forwarding to backup DNS. It changes real
DNS records, uses the returned IPs to test each edge with verified HTTPS,
observes expiry, and manually flushes the client cache with SIGHUP. It restores
both DNS records and stops the temporary cache in a finally block. Its current
SSH settings target this lab session. This test does not exercise the macOS
system resolver; primary-stop OS failover must be demonstrated separately.

## End of demonstration

To repeat the three Phase 1 failure cases from Mac 1, run
`/usr/bin/python3 phase2/phase1-failures.py`. It exercises a wrongly configured
temporary client resolver on each Mac, real wrong DNS records with standby
nginx stopped, and both backends stopped. It restores DNS, the standby and both
backends and verifies A/B recovery. Evidence is in
`evidence/phase-1/failures-2026-11-22/`. This test does not change global DNS
preferences or firewall/trust settings.

On both Macs run `dns-primary`, `dns-start`, `firewall-off`, and `cache-flush`.
Restore both backends and verify A/B responses through Mac 2. Existing TCP
connections can outlive DNS TTL, so use new curl processes for cutover evidence.

To remove the password-free access later, locally run
`sudo rm /private/etc/sudoers.d/cn-project` on each Mac. Stop project DNS and
remove the PF rules before uninstalling its admin rule. Restore the saved
resolver file from `/private/var/db/cn-project/resolver.original` if desired.
Revoke Kavya's dedicated public key in Ronit's `~/.ssh/authorized_keys` after
the project if further remote access is no longer needed.
