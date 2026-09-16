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

**Terminal 1 (Publisher/Server):**
`ash
source ~/quic-env/bin/activate
cd ~/QUIC-Benchmark-Testing
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
=== MoQ Pub/Sub Server ===
Topic: dinesh/in
Waiting for subscriber on port 4434...
[Server] Subscriber connected for topic: dinesh/in
[Server] Starting to publish 1-10000 on topic: dinesh/in
[Server] Sent: 1000
[Server] Sent: 2000
...
[Server] Sent: 10000
[Server] Done! Published 10000 messages.
`

**Expected Output (Client):**
`
=== MoQ Pub/Sub Client ===
Connecting to server...
[Client] Subscribed to topic: dinesh/in
[Client] Waiting for messages...
[Client] Received: 1
[Client] Received: 2
[Client] Received: 3
[Client] Received: 4
[Client] Received: 5
[Client] Received: 1000
...
[Client] Received: 10000

============ RESULTS ============
Total received: 10000
First: 1
Last: 10000
Sequence check: CORRECT (1 to 10000 in order)
`

---

## Project Structure

`
QUIC-Benchmark-Testing/
├── README.md                 # This file
├── QUIC_Benchmark_Report.md  # Detailed project report
├── server.py                 # Basic QUIC server (interoperability test)
├── client.py                 # Basic QUIC client (interoperability test)
├── benchmark.py              # QUIC benchmark script
├── moq_server.py             # MoQ Publisher server
└── moq_client.py             # MoQ Subscriber client
`

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

## References

- [RFC 9000 - QUIC Protocol](https://datatracker.ietf.org/doc/html/rfc9000)
- [aioquic - Python QUIC Library](https://github.com/aiortc/aioquic)
