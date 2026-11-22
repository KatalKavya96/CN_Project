# Corrected capture checks for PR #1

Prepared 23 November 2026. All seven saved PCAPs passed the corrected visible
sequence checks. The new TLS 1.2 supplement also contains a Certificate message
and has a separate certificate-verified HTTP 200 curl log.

| Capture | Matching visible streams |
| --- | --- |
| Original baseline | 1 |
| Original final | 35 |
| Original cutover recheck | 3 |
| Three-Mac final | 44 |
| Three-Mac protocol capture | 1 |
| TLS 1.2 Certificate supplement | 1; explicitly DNS-independent |
| Latest live rehearsal | 36 |

These counts are not counts of cryptographically verified handshakes or HTTP
successes. See `summary.json` and the per-capture JSON for exact frame numbers,
capture hashes and scope. For TLS 1.3 the checker labels encrypted records only;
it never infers Finished, HTTP content or alerts from record length/count.

## Corrections to the original PR

- DNS query/response must match the TCP client and edge and precede the SYN.
  The original code accepted a DNS reply for another client or one appearing
  after the TCP/TLS exchange. The reordered-DNS regression now fails as expected.
- TShark handles record/message reassembly, including a Certificate coalesced
  into the same TLS record as ServerHello. No custom TLS decryptor is claimed.
- The checker refuses output paths that replace a capture or any existing file.
- The TLS 1.2 capture script uses a unique directory, retains certificate
  verification, requires HTTP 200, and never changes a live service setting.
- The original PR's generated reports and old source hashes were not imported;
  this folder records fresh results against the corrected implementation.

`regression-tests.txt` records ten passing tests, including negative DNS order,
client/address matching, encrypted-certificate visibility, coalesced TLS 1.2
messages, early resets and preservation of existing output files.

The repository cleanup removes obsolete repair/scaffold scripts and generated
CSR/serial artifacts. Existing raw evidence and PDF bytes remain unchanged.
Runtime configurations, certificates and keys are preserved; ordinary access
logs may grow when verification requests are made. See `preservation.json`.

The corrected checker requires TShark (installed with Wireshark). This replaces
the PR's dependency-free custom parser in exchange for established protocol
reassembly and accurately limited claims. The
[capture guide](../../../docs/capture-evidence.md) explains commands and limits.
