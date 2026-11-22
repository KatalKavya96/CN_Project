# Live Setup Recovery - 23 November 2026

## Observed cause and action

Ronit's saved address still answered ping, but SSH, backup DNS and HTTPS were
intermittently unavailable. A standard wake packet restored authenticated SSH.
The recovered Mac reported battery power and `AppleClamshellState = Yes`
(closed lid). Backend A and nginx were still listening; the tracked repository
configuration was intact. A subsequent check confirmed the lid was open.
The observation is consistent with sleep/network-wake behavior; no destructive
reset or certificate regeneration was needed.

Temporary `caffeinate -dimsu` processes were started on both Macs. Their PIDs
are saved under each host's ignored `.runtime/keep-awake.pid`. Keep both lids
open and connect both chargers for the demo. A keep-awake assertion does not
guarantee availability after a forced sleep, closed lid, or exhausted battery.
Ronit's recovery power reading still showed battery power.

## Restored normal state

- Both DNS services are running and both project names point to Mac 2.
- Both clients' caches were flushed after record restoration.
- Both backends are running; GET /, GET /api/status and HEAD pass on each host.
- Primary nginx on Mac 2 and standby nginx on Mac 1 are available.
- Eight requests from each client through each edge observe both A and B.
- Both hostnames pass plain default-trust HTTPS on both Macs.
- Temporary project firewall rules are removed; final rule states are logged.

New logs are under `evidence/recovery/2026-11-23T015853/`. The original 137
evidence files were hashed before and after the live recovery and were
unchanged. Original raw logs/captures are retained; the derived submission
index is updated separately to link the new recovery evidence.

## Repeating recovery

With both Macs open, powered, on the recorded addresses and reachable by SSH:

```bash
cd /Users/kavyakatal/Desktop/CN_Project
/usr/bin/python3 phase2/recover-live.py
```

The script writes a new timestamped folder. It restores existing managed
services and verifies the live setup; it does not delete evidence, regenerate
certificates, or modify global firewall rules. It expects both nginx instances
to be running. If nginx is stopped, use the startup instructions in
`docs/tomorrow-demo.md`, then rerun the verifier.

This recovery is a return to the normal live state, not a replacement for the
recorded controlled failure tests or a guarantee of future hardware availability.
