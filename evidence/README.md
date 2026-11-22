# Evidence for Both Project Phases

Start with the [requirements index](submission/README.md) or download/open the
[browsable evidence book](submission/evidence-book.html). They map all seven
Phase 1 build tasks, all five required Phase 1 failures, all six Phase 2
extensions, and the final deliverables to their original files.

The sources are actual command exports and packet captures. Their original
test timestamps are retained. The evidence book displays log excerpts and
does not represent them as screenshots of a live terminal.

- `submission/manifest.json`: source paths, byte counts, and SHA-256 hashes.
- `submission/*packets.tsv`, `protocol-flow.tsv`, `tcp-reliability.tsv`: real
  TShark exports of the original single-request capture, including ports,
  sequence/acknowledgement numbers, DNS answers, SNI and TLS records.
- `submission/configuration-bundle.txt`: public configuration sources and
  the generated Mac 1 nginx config, with no private key contents.
- `phase-1/failures-2026-11-22/`: both-client failure demonstrations and recovery.
- `phase-2/acceptance-summary.md`: final integrated acceptance results.
- `phase-2/final-cutover-recheck/`: measured successful OS-cache cutover recheck.

Scope notes are preserved: wrong DNS uses a temporary client-scoped resolver;
independent Backend B rejection needs an unrelated third source IP; faculty
challenge, spoken presentation and viva must happen during evaluation.
Fresh direct-root Backend A evidence and final remote Git synchronization
depend on restoring SSH access to Ronit's Mac. Earlier passing remote results
are historical observations, not a claim that the current connection is healthy.
