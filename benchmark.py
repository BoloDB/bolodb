import asyncio
import time
import httpx
import uvicorn
import multiprocessing

def run_server():
    uvicorn.run("app.server:create_app", factory=True, host="127.0.0.1", port=8000, log_level="critical")

async def load_test():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
        # Warmup
        for _ in range(10):
            await client.get("/")

        start = time.time()
        # 1000 concurrent requests
        tasks = [client.get("/") for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start

        print(f"Completed 1000 requests in {duration:.4f} seconds")
        print(f"Requests per second: {1000/duration:.2f}")

if __name__ == "__main__":
    server_process = multiprocessing.Process(target=run_server)
    server_process.start()

    time.sleep(2) # wait for server to start

    try:
        asyncio.run(load_test())
    finally:
        server_process.terminate()
        server_process.join()
