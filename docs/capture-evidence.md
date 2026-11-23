# Packet evidence and the Certificate message

The original captures and verified curl logs remain unchanged. PR #1's proposed
checker was corrected before integration: its original encrypted-record labels
were heuristics, and a DNS answer for another client or after a TCP connection
could incorrectly satisfy its supposed ordered-chain check.

The [corrected check results](../evidence/phase-2/capture-checks-20261123T103704/README.md)
cover all seven PCAPs and ten regression tests.

## What the corrected checker establishes

`phase2/check-capture.py` uses TShark from the installed Wireshark distribution.
It requires a matching IPv4 UDP DNS query/response for the same client and edge
before that TCP stream's SYN, a three-way TCP handshake, matching ClientHello
SNI, ServerHello, and visible encrypted records in both directions. Wireshark
handles TCP reassembly and handshake messages coalesced into a TLS record.

PASS is labelled **VISIBLE PACKET SEQUENCE ONLY**. It does not identify encrypted
TLS 1.3 Finished, alerts or HTTP messages, establish certificate trust, or prove
an HTTP 200 response. TLS 1.3 hides the inner content type, and record padding
prevents reliable message identification from record length. Pair packet facts
with the certificate-verified curl output. See
[RFC 8446, section 5.2](https://www.rfc-editor.org/rfc/rfc8446.html#section-5.2)
and [record padding](https://www.rfc-editor.org/rfc/rfc8446.html#section-5.4).

```bash
/usr/bin/python3 phase2/check-capture.py evidence/phase-2/baseline/dns-tcp-tls-current.pcap
```

For a deliberately DNS-independent capture, `--skip-dns --edge ADDRESS` explicitly
removes the DNS requirement. This must not be described as proof of DNS or
resolver fallback. Existing captures and output files cannot be overwritten by
the checker's output options. IPv6 and DNS-over-TCP correlation are outside the
current checker scope; TShark still reads standard pcap/pcapng containers.

## Verified live TLS 1.2 supplement

The new live capture is in
`evidence/phase-2/tls12-certificate-20261123T103526-hb_yht3c/`.
Its `summary.json` records HTTP 200, certificate verification and a visible
Certificate message. It negotiated TLS 1.2 for one request to the existing edge;
no nginx, DNS, trust, backend or firewall configuration was changed.

Kavya can open it with:

```bash
open -a Wireshark evidence/phase-2/tls12-certificate-20261123T103526-hb_yht3c/tls12-handshake.pcap
```

Useful display filters:

```text
tls.handshake.type == 1
tls.handshake.type == 2
tls.handshake.type == 11
tls.record.content_type == 20
```

Type 11 is the Certificate handshake message. Expand its certificate details to
inspect the issuer and subject/SAN information. Our normal TLS 1.3 connections
encrypt that message; the absence of a plaintext Certificate there is expected.

To collect a separate new supplement on Kavya's Mac:

```bash
/usr/bin/python3 phase2/capture-tls12.py
```

This requires the existing public CA file, tcpdump access and TShark. It forces
TLS 1.2 for that request, retains verification, uses an explicit destination,
and creates a unique folder. The pcap proves visible messages; its paired curl
log supplies the separate certificate-verification and HTTP-status evidence.
