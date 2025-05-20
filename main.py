import os
import json
import base64
import asyncio
import keep_alive
import httpx
import uvicorn
from urllib.parse import urlparse, urlunparse
from curl_cffi import requests as curl_requests
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient, Timeout
from pydantic import BaseSettings


class Settings(BaseSettings):
    MAX_PROXY_DEPTH: int = int(os.getenv("MAX_PROXY_DEPTH", 5))
    REQUEST_TIMEOUT_MS: int = int(os.getenv("REQUEST_TIMEOUT_MS", 60000))
    PROXY_CHAIN: str = 'x-proxy-chain'
    LOOP_COUNT: str = 'x-loop-count'
    TARGET_URL: str = 'x-target-url'
    HASH_AUTH: str = (os.getenv("HashAuth") or "").lower()
    HTTP_TYPE: str = 'x-http'

    HEADERS_TO_DELETE: set = {
        'sozu-id', 'traceparent', 'x-amzn-trace-id', 'cdn-loop',
        'cf-connecting-ip', 'cf-ew-via', 'cf-ray', 'cf-visitor',
        'cf-worker', 'cf-ipcountry', 'x-forwarded-for', 'x-forwarded-host',
        'x-real-ip', 'forwarded', 'client-ip', 'x-max-bytecode-size',
        'x-min-bytecode-size', 'x-vercel-deployment-url', 'x-vercel-forwarded-for',
        'x-vercel-id', 'x-vercel-internal-ingress-bucket', 'x-vercel-internal-intra-session',
        'x-vercel-ip-as-number', 'x-vercel-ip-city', 'x-vercel-ip-continent',
        'x-vercel-ip-country', 'x-vercel-ip-latitude', 'x-vercel-ip-longitude',
        'x-vercel-ip-timezone', 'x-vercel-ja4-digest', 'x-vercel-proxied-for',
        'x-vercel-proxy-signature', 'x-vercel-ip-postal-code',
        # custom header for choosing http lib
        'x-http',
    }

    @property
    def CONFIG_TO_DELETE(self) -> set:
        return {
            self.HASH_AUTH,
            self.PROXY_CHAIN,
            self.TARGET_URL,
            self.LOOP_COUNT,
            self.HTTP_TYPE,
        } | self.HEADERS_TO_DELETE


settings = Settings()
app = FastAPI(title="Chain Proxy Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_http_client() -> AsyncClient:
    return AsyncClient(
        timeout=Timeout(settings.REQUEST_TIMEOUT_MS / 1000),
        follow_redirects=True,
        http2=True,
        limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
    )


async def proxy_request(request: Request) -> Response:
    loop_count = int(request.headers.get(settings.LOOP_COUNT, '0'))
    if loop_count >= settings.MAX_PROXY_DEPTH:
        raise HTTPException(status_code=400, detail=f"Proxy depth exceeds maximum ({settings.MAX_PROXY_DEPTH})")

    encoded_chain = request.headers.get(settings.PROXY_CHAIN)
    try:
        proxy_chain = json.loads(base64.b64decode(encoded_chain)) if encoded_chain else []
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid x-proxy-chain header")

    target_url = request.headers.get(settings.TARGET_URL)

    if proxy_chain:
        forward_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in settings.HEADERS_TO_DELETE
        }
        forward_headers[settings.LOOP_COUNT] = str(loop_count + 1)
        next_target = proxy_chain.pop(0)
        if proxy_chain:
            forward_headers[settings.PROXY_CHAIN] = base64.b64encode(json.dumps(proxy_chain).encode()).decode()
    else:
        forward_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in settings.CONFIG_TO_DELETE
        }
        next_target = target_url

    if not next_target:
        raise HTTPException(status_code=400, detail="Missing x-target-url header for final hop")

    parsed = urlparse(next_target)
    forward_headers['host'] = parsed.netloc
    forward_headers.pop(settings.HTTP_TYPE, None)
    body = await request.body()
    use_httpx = request.headers.get(settings.HTTP_TYPE, 'curl').lower() == 'httpx'

    try:
        if use_httpx:
            async with await get_http_client() as client:
                resp = await client.request(
                    method=request.method,
                    url=next_target,
                    headers=forward_headers,
                    content=body,
                )
        else:
            def sync_call():
                return curl_requests.request(
                    method=request.method,
                    url=next_target,
                    headers=forward_headers,
                    data=body,
                    timeout=settings.REQUEST_TIMEOUT_MS / 1000
                )

            resp = await asyncio.get_event_loop().run_in_executor(None, sync_call)

        status, content, resp_headers = resp.status_code, resp.content, resp.headers
        resp_headers_dict = {k: v for k, v in resp_headers.items() if k.lower() != 'content-length'}
        return Response(content=content, status_code=status, headers=resp_headers_dict)
    except Exception as e:
        raise HTTPException(status_code=502, detail="Bad Gateway")


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def handle_request(request: Request, path: str):
    if settings.HASH_AUTH and settings.HASH_AUTH not in request.headers:
        raise HTTPException(status_code=403, detail="Missing authentication header")
    return await proxy_request(request)


if __name__ == "__main__":
    import platform

    config = {
        "app": "loop2:app",
        "host": "0.0.0.0",
        "port": 8000,
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
        "access_log": False,
    }
    if platform.system().lower() != "windows":
        config.update({"loop": "uvloop", "http": "httptools"})
    uvicorn.run(**config)
