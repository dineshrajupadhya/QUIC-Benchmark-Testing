import asyncio
import sys
import os

async def run_test():
    print("=" * 60)
    print("  Testing MoQ Protocol Implementation")
    print("=" * 60)
    
    print("\n[1] Starting MoQ Server...")
    server_proc = await asyncio.create_subprocess_exec(
        sys.executable, "moq_server.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    await asyncio.sleep(3)
    
    print("[2] Starting MoQ Client...")
    client_proc = await asyncio.create_subprocess_exec(
        sys.executable, "moq_client.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(client_proc.communicate(), timeout=60)
        print("\n=== CLIENT OUTPUT ===")
        print(stdout.decode())
    except asyncio.TimeoutError:
        print("[Test] Client timed out")
    
    server_proc.terminate()
    try:
        stdout, stderr = await asyncio.wait_for(server_proc.communicate(), timeout=5)
        print("\n=== SERVER OUTPUT ===")
        print(stdout.decode())
    except asyncio.TimeoutError:
        server_proc.kill()
    
    print("\n" + "=" * 60)
    print("  Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_test())
