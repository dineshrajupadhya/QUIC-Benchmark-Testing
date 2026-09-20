# QUIC Protocol - Benchmark, Interoperability & MoQ Pub/Sub Testing

## Overview

This project demonstrates:
1. **QUIC Benchmark Testing** - Measuring connection latency
2. **Interoperability Testing** - Client-Server communication over QUIC
3. **MoQ (Media over QUIC) Pub/Sub** - Publish/Subscribe system for video streaming

---

## Prerequisites

### System Requirements
- Windows 10/11 with WSL2 enabled
- Ubuntu 20.04+ on WSL2
- Docker Desktop (with WSL2 integration)
- Internet connection

### Required Software (already installed)

| Software | Version | Purpose |
|----------|---------|---------|
| GCC | 15.2.0 | C/C++ compiler |
| CMake | 4.2.3 | Build system |
| OpenSSL | 3.5.5 | TLS/SSL library |
| Python | 3.14 | Programming language |
| Rust | 1.98.1 | For building ngtcp2 |
| Docker | Latest | Container runtime |

---

## Quick Start Guide

### Step 1: Open Ubuntu Terminal

**IMPORTANT:** All commands must be run in **Ubuntu Terminal**, NOT Windows PowerShell.

To open Ubuntu:
1. Press Windows Start button
2. Type **Ubuntu** and press Enter

---

### Step 2: Activate Python Environment

`ash
source ~/quic-env/bin/activate
`

### Step 3: Navigate to Project

`ash
cd ~/QUIC-Benchmark-Testing
`

---

## Running the Tests

### Test 1: QUIC Interoperability Test

**Terminal 1 (Server):**
`ash
source ~/quic-env/bin/activate
cd ~/QUIC-Benchmark-Testing
python3 server.py
`

**Terminal 2 (Client):**
`ash
source ~/quic-env/bin/activate
cd ~/QUIC-Benchmark-Testing
python3 client.py
`

**Expected Output:**
`
Connected to server via QUIC!
Interoperability test PASSED!
`

---

### Test 2: QUIC Benchmark Test

`ash
source ~/quic-env/bin/activate
cd ~/QUIC-Benchmark-Testing
python3 benchmark.py
`

**Expected Output:**
`
=== QUIC Benchmark Results ===
Connections: 10
Average latency: 138.50 ms
Min latency: 120.62 ms
Max latency: 159.16 ms
`

---

### Test 3: MoQ Pub/Sub System

**IMPORTANT:** Generate certificates first, then start server, then client.

#### Option A: Single Terminal (Easy)

`ash
source ~/quic-env/bin/activate
cd ~/QUIC-Benchmark-Testing

# Generate certificates
mkdir -p /tmp/aioquic/examples
openssl req -x509 -newkey rsa:4096 -keyout /tmp/aioquic/examples/key.pem -out /tmp/aioquic/examples/cert.pem -days 365 -nodes -subj '/CN=localhost' -addext 'subjectAltName = DNS:localhost, IP:127.0.0.1'

# Run server in background, then client
python3 moq_server.py &
sleep 3
python3 moq_client.py
kill %1
`

#### Option B: Two Terminals (See Both Outputs)

**Terminal 1 (Publisher/Server):**
`ash
source ~/quic-env/bin/activate
cd ~/QUIC-Benchmark-Testing

# Generate certificates (only needed once per session)
mkdir -p /tmp/aioquic/examples
openssl req -x509 -newkey rsa:4096 -keyout /tmp/aioquic/examples/key.pem -out /tmp/aioquic/examples/cert.pem -days 365 -nodes -subj '/CN=localhost' -addext 'subjectAltName = DNS:localhost, IP:127.0.0.1'

# Start server
python3 moq_server.py
`

**Terminal 2 (Subscriber/Client):**
`ash
source ~/quic-env/bin/activate
cd ~/QUIC-Benchmark-Testing
python3 moq_client.py
`

**Expected Output (Server):**
`
============================================================
  MoQ Transport Publisher Server
  Based on draft-ietf-moq-transport-21
============================================================
  Topic: dinesh/in
  Messages: 1-10000
  Listening on: 0.0.0.0:4434
  Protocol: QUIC + MoQT (version 0x00000001)
  ALPN: moqt

  Flow:
  1. Wait for subscriber connection
  2. Verify subscriber is subscribed
  3. Check subscriber availability
  4. Publish messages only if subscribers exist
============================================================

[Server] Started on 0.0.0.0:4434
[Server] Waiting for subscriber to connect and subscribe...

[Server] QUIC handshake completed
[Server] Connection status: CONNECTED
[Server] CLIENT_SETUP received
[Server] SERVER_SETUP sent
[Server] MoQ handshake complete!
[Server] SUBSCRIBE received: namespace=dinesh/in, track=stream-1
[Server] SUBSCRIBE_OK sent
[Server] Active subscribers: 1
[Server] Subscriber connected BEFORE publishing started!
[Server] Queuing 10000 messages for subscriber...
[Server] Published: 1 (1/10000)
[Server] Published: 1000 (1000/10000)
...
[Server] Published: 10000 (10000/10000)
[Server] Done! Published 10000 messages.
[Server] Scenario verified: subscriber received all messages!
`

**Expected Output (Client):**
`
============================================================
  MoQ Transport Subscriber Client
  Based on draft-ietf-moq-transport-21
============================================================

[Client] --- Connection Check ---
[Client] Target server: 127.0.0.1:4434
[Client] Certificate found: OK
[Client] ------------------------

[Client] Attempting to connect to publisher...

[Client] --- Connection Established ---
[Client] Connected to 127.0.0.1:4434
[Client] QUIC handshake: SUCCESS
[Client] --------------------------------

[Client] CLIENT_SETUP sent
[Client] SERVER_SETUP received
[Client] MoQ handshake: COMPLETE

[Client] --- Subscribe Check ---
[Client] Topic: dinesh/in
[Client] Track: stream-1
[Client] Filter: LATEST
[Client] SUBSCRIBE sent
[Client] SUBSCRIBE_OK received
[Client] Subscription status: ACTIVE
[Client] -------------------------

[Client] Waiting for publisher to publish messages...

[Client] Received: 1 (1/10000)
[Client] Received: 1000 (1000/10000)
...
[Client] Received: 10000 (10000/10000)
[Client] PUBLISH_DONE: All messages published

============================================================
  RESULTS
============================================================
  Total received: 10000
  First: 1
  Last: 10000
  Time taken: 0.555s
  Throughput: 18003 messages/sec
  Sequence: CORRECT (1 to 10000 in order)

  Scenario: Subscriber connected BEFORE publisher
  published any messages. Server waited for SUBSCRIBE
  then sent all 10000 messages to the subscriber.
============================================================
`

---

## MoQ Protocol Flow

The system implements **draft-ietf-moq-transport-21** with:

1. **CLIENT_SETUP / SERVER_SETUP** - MoQ version negotiation
2. **SUBSCRIBE / SUBSCRIBE_OK** - Subscriber registers interest in topic
3. **PUBLISH / PUBLISH_OK** - Publisher sends objects to subscriber
4. **PUBLISH_DONE** - All objects delivered

**Key Feature:** Subscriber can connect BEFORE publisher publishes. Server waits for SUBSCRIBE before sending any messages.

`
Subscriber           Publisher
   |                    |
   |--- CLIENT_SETUP -->|
   |<-- SERVER_SETUP ---|
   |--- SUBSCRIBE ----->|
   |<-- SUBSCRIBE_OK ---|
   |                    | (publisher starts sending)
   |<-- PUBLISH (x10000)|
   |--- PUBLISH_OK ---> |
   |<-- PUBLISH_DONE ---|
`

---

---

## Project Structure

`
QUIC-Benchmark-Testing/
├── README.md                    # This file
├── QUIC_Benchmark_Report.md     # Detailed project report
├── server.py                    # Basic QUIC server (interoperability test)
├── client.py                    # Basic QUIC client (interoperability test)
├── benchmark.py                 # QUIC benchmark script
├── moq_protocol.py              # MoQ protocol module (varints, message types, parser)
├── moq_server.py                # MoQ Publisher server
├── moq_client.py                # MoQ Subscriber client
└── test_subscriber_first.py     # Test: subscriber subscribes before publisher publishes
`

---

---

## Troubleshooting

### Issue: Certificate errors
**Solution:** Regenerate certificates:
`ash
openssl req -x509 -newkey rsa:4096 -keyout /tmp/key.pem -out /tmp/cert.pem -days 365 -nodes -subj '/CN=localhost' -addext 'subjectAltName = DNS:localhost, IP:127.0.0.1'
`

### Issue: Module not found (aioquic)
**Solution:** Activate virtual environment:
`ash
source ~/quic-env/bin/activate
`

### Issue: Connection refused
**Solution:** Make sure server is running before starting client.

---

## Results Summary

| Test | Status | Key Finding |
|------|--------|-------------|
| Interoperability | PASSED | Client-Server communication works |
| Benchmark | PASSED | Avg latency 138.50ms |
| MoQ Pub/Sub | PASSED | 10000 messages received in order |

---

## Author

**Dinesh Raj Upadhya**
Email: dineshrajupadhya86@gmail.com
GitHub: https://github.com/dineshrajupadhya

---

## RFC Standards & Compliance

This project implements protocols based on the following RFC standards and drafts:

### QUIC Protocol (Implemented & Tested)

| RFC | Title | Status | Description |
|-----|-------|--------|-------------|
| [RFC 9000](https://datatracker.ietf.org/doc/html/rfc9000) | QUIC: A UDP-Based Multiplexed and Secure Transport | **Official RFC** (May 2021) | Core QUIC protocol specification |
| [RFC 9001](https://datatracker.ietf.org/doc/html/rfc9001) | Using TLS to Secure QUIC | **Official RFC** (May 2021) | TLS 1.3 integration with QUIC |
| [RFC 9002](https://datatracker.ietf.org/doc/html/rfc9002) | QUIC Loss Detection and Congestion Control | **Official RFC** (May 2021) | Reliability and flow control |
| [RFC 9003](https://datatracker.ietf.org/doc/html/rfc9003) | Connection Migration in QUIC | **Official RFC** (May 2021) | Connection ID based migration |

### MoQ Transport Protocol (Implemented & Tested)

| Document | Title | Status | Description |
|----------|-------|--------|-------------|
| [draft-ietf-moq-transport-21](https://datatracker.ietf.org/doc/draft-ietf-moq-transport/) | Media over QUIC Transport | **Draft** (21st revision) | MoQ transport protocol specification |

**Note:** MoQ (Media over QUIC) is still under development as an IETF draft. It has not yet been published as an official RFC. Our implementation follows the latest available draft (revision 21).

### What is an RFC?

**RFC (Request for Comments)** is the official publication channel for Internet standards. Published by the **IETF (Internet Engineering Task Force)**, RFCs define how protocols should work.

- **Proposed Standard**: New protocol specification
- **Draft**: Working document, not yet official (like MoQ)
- **Internet Standard (STD)**: Mature, widely implemented specification

### What is an Internet Draft?

An **Internet Draft** is a working document of the IETF. It is **not** a standard - it is a proposal being developed. `draft-ietf-moq-transport-21` means:
- `draft` = Working document
- `ietf` = IETF working group (not individual submission)
- `moq` = Media over QUIC working group
- `transport` = Protocol name
- `21` = 21st revision of this draft

### Our Implementation Compliance

| Component | Standard | Compliance |
|-----------|----------|------------|
| QUIC Transport | RFC 9000 | Full compliance via aioquic library |
| QUIC Security (TLS 1.3) | RFC 9001 | Full compliance via aioquic library |
| MoQ Handshake | draft-ietf-moq-transport-21 | CLIENT_SETUP/SERVER_SETUP with version negotiation |
| MoQ Subscribe | draft-ietf-moq-transport-21 | SUBSCRIBE/SUBSCRIBE_OK with namespace and track |
| MoQ Publish | draft-ietf-moq-transport-21 | PUBLISH/PUBLISH_OK with object delivery |
| MoQ Varint Encoding | draft-ietf-moq-transport-21 | QUIC-style variable-length integers |
| MoQ ALPN | draft-ietf-moq-transport-21 | Protocol identifier: "moqt" |

### References

- [IETF QUIC Working Group](https://datatracker.ietf.org/wg/quic/documents/)
- [IETF MoQ Working Group](https://datatracker.ietf.org/wg/moq/documents/)
- [RFC Editor](https://www.rfc-editor.org/)
- [aioquic - Python QUIC Library](https://github.com/aiortc/aioquic)
- [MoQ Transport Draft](https://datatracker.ietf.org/doc/draft-ietf-moq-transport/)
