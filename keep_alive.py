# keep_alive.py
import time
import httpx
import os

url = f"https://{os.environ.get('PROJECT_DOMAIN')}/health"
while True:
    try:
        httpx.get(url).close()
        print("Keeping alive...")
    except:
        print("Failed to keep alive")
    time.sleep(5 * 60)  # 每5分钟请求一次
