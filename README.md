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
2. Type 
