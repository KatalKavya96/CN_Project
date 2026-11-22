# End-to-End Request Flow

This document follows one request to:

```text
https://app.cn-project.test:8443/api/status
```

## 1. DNS Resolution

DNS server:

```text
10.7.26.228:53
```

Query:

```text
A app.cn-project.test
```

Answer:

```text
10.7.18.166
```

TTL:

```text
30 seconds
```

DNS maps the hostname to the nginx edge IP address. It does not create a connection or send the HTTP request. After DNS resolution, the client knows that `app.cn-project.test` should be reached at `10.7.18.166`. Phase 2 clients also list backup DNS `10.7.26.237:53` on Priyanshu's Mac; during controlled cutover, both DNS servers point the name to standby edge `10.7.26.228`.

## 2. TCP Connection

The client opens a TCP connection from an ephemeral local port to the nginx HTTPS listener:

```text
client ephemeral port -> 10.7.18.166:8443
```

TCP uses a three-way handshake:

```text
SYN
SYN-ACK
ACK
```

After the handshake completes, TCP provides a reliable, ordered, connection-oriented byte stream between the client and nginx.

## 3. TLS Handshake

TLS begins after the TCP connection is established. The handshake includes:

```text
ClientHello
SNI=app.cn-project.test
ServerHello
certificate
certificate verification
```

The client sends SNI so nginx can present the certificate for `app.cn-project.test`. The server certificate is signed by the local CA, and the client verifies it using the trusted public CA certificate.

The actual successful proof command is:

```bash
/usr/bin/curl --cacert .runtime/ca.crt -v https://app.cn-project.test:8443
```

The expected verification line is:

```text
SSL certificate verify ok.
```

Final proof must not use `-k`, because `-k` disables certificate verification.

## 4. HTTP Request

After TLS is established, the client sends the HTTP request inside the encrypted TLS session:

```http
GET /api/status HTTP/1.1
Host: app.cn-project.test:8443
```

In Wireshark, the HTTP request body and headers are not visible as plaintext on the wire. They appear inside encrypted TLS Application Data.

## 5. nginx Reverse Proxy / Load Balancing

nginx receives the decrypted HTTP request at the edge and forwards it to one upstream backend.

```text
Backend A -> 127.0.0.1:3001
Backend B -> 10.7.26.228:3002
```

The upstream selection uses round-robin load balancing. Repeated requests alternate between Backend A and Backend B when both are healthy. The `X-Backend` response header identifies which backend handled the request.

## 6. HTTP Caching

Both backends return cache headers:

```http
Cache-Control: max-age=60
ETag: "A-v1" or "B-v1"
```

The client can reuse a fresh cached response for up to 60 seconds. For validation, the client can send `If-None-Match` with a previous ETag. If the backend resource has not changed, the server returns:

```http
304 Not Modified
```

This proves HTTP caching behavior without sending a new response body.

## 7. Response Path

The response follows the reverse path:

```text
Backend
-> nginx
-> TLS
-> TCP
-> LAN
-> client
```

The backend generates the HTTP response, nginx forwards it through the established TLS session, TCP delivers the encrypted bytes across the LAN, and the client decrypts and displays the final HTTP result.
