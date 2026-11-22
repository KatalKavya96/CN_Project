# Mac 3 as Phase 2 Backup DNS

Active backup: Priyanshu Tomar, `priyanshutomar@10.7.26.237`, arm64, dnsmasq 2.93.
Only backup DNS moves. Primary DNS, both backends, both edges and TLS stay put.

The new helpers are DNS-only, root-owned, and expose exact actions. They do
not grant a general shell or modify existing backend/firewall helpers.

One local administrator authentication is required on each Mac to install:

```bash
# Kavya's Mac
cd /Users/kavyakatal/Desktop/CN_Project
bash phase2/install-mac3-dns.sh mac1
```

```bash
# Ronit's Mac
cd /Users/ronitsingh/Desktop/CN_Project
bash phase2/install-mac3-dns.sh mac2
```

```bash
# Priyanshu's Mac
cd /Users/priyanshutomar/CN_Project
bash phase2/install-mac3-dns.sh mac3
```

Installation does not change existing client resolver addresses. Mac 3 starts its
candidate DNS on its own LAN address only. If port 53 conflicts with Internet
Sharing, no clients are switched and the existing backup remains available.
Do not stop mDNSResponder. In the actual installation, DNS bound to Mac 3's
LAN IP coexists with Internet Sharing; sharing was left enabled and unchanged.

After candidate DNS passes direct tests from both clients, activate using
`sudo -n /usr/local/sbin/cn-project-resolver use-mac3` on Macs 1 and 2.
Rollback is `use-mac2`. Test real primary-stop resolver failover and restoration
before retiring Mac 2's legacy DNS. Update `BACKUP_DNS_IP` in `lab.env` only
after successful activation, so the Python DNS-control router selects Mac 3.

Mac 3 controls are `sudo -n /usr/local/sbin/cn-project-backup ACTION`, where
ACTION is `dns-start`, `dns-run` (foreground), `dns-stop`, `dns-primary`,
`dns-standby`, or `dns-status`. Both DNS record changes must reach Mac 1 and
Mac 3. The adapted orchestration also keeps retired Mac 2's records aligned
for quick rollback without restarting that legacy resolver.

The SSH host keys in `ssh-known-hosts` were checked against locally reported
fingerprints. Mac 3 received no TLS private key and needs no Codex account.

## Active state and rollback

Both clients now use Mac 1 primary and Mac 3 backup. The legacy Mac 2 DNS is
stopped, with its settings retained. Fresh evidence is in
`evidence/phase-2/mac3-dns/`. Both clients passed uncached OS resolution and
plain HTTPS with primary DNS and legacy backup simultaneously stopped.

To undo the migration, first start the original backup on Ronit's Mac with
`sudo -n /usr/local/sbin/cn-project-admin dns-primary` then `dns-start`.
On both client Macs run `sudo -n /usr/local/sbin/cn-project-resolver use-mac2`.
Set `BACKUP_DNS_IP=10.7.18.166` in `phase2/lab.env` before using the Python
orchestrators again. Keep primary DNS running; verify both names and HTTPS
before stopping Mac 3. No certificate, edge, backend, or old evidence needs
changing. The installer refuses overwriting an existing installation.
