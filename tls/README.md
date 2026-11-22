# Project TLS configuration

The live edges use `.runtime/server.crt`, `.runtime/server.key` and
`.runtime/ca.crt`. Each edge has its own private key and a server certificate
covering `app.cn-project.test` and `api.cn-project.test`. The shared local CA's
private key remains on Ronit's Mac. Both original client Macs trust its public
certificate; Priyanshu's DNS-only role needs no TLS keys.

`openssl.cnf` and `generated/server.ext` are public certificate configuration
references. CSR and CA serial files are generated artifacts and are ignored.
No live certificate, private key, CA trust or nginx configuration was changed
by removing the obsolete certificate repair scripts.

## Provisioning model

For a new deployment, generate the local CA on its designated owner, generate
a separate edge private key and CSR on each edge, and sign each CSR with the
existing CA and SAN/server-auth extensions. Return the signed server certificate
to its edge and distribute only the public CA certificate to clients for
approved trust installation. Do not regenerate the CA or replace certificates
on this working deployment merely to prepare a demonstration.

## Read-only verification on either edge

From that Mac's repository root:

```bash
openssl x509 -in .runtime/server.crt -noout -subject -issuer -dates
openssl x509 -in .runtime/server.crt -noout -text
openssl verify -CAfile .runtime/ca.crt .runtime/server.crt
/usr/bin/curl --noproxy '*' -v https://app.cn-project.test:8443/api/status
```

The certificate must contain both DNS SANs, and the normal HTTPS request must
verify successfully. `-k` does not prove certificate trust. Our existing TLS 1.3
captures encrypt the Certificate message; a verified TLS 1.2 capture can be a
separate supplementary demonstration when the Certificate must be shown in clear.
