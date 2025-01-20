import os
import json
import base64
import httpx
import uvicorn
import keep_alive

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient, Timeout
from pydantic import BaseSettings
from urllib.parse import urlparse


class Settings(BaseSettings):
    MAX_PROXY_DEPTH: int = os.environ.get("MAX_PROXY_DEPTH", 5)
    REQUEST_TIMEOUT_MS: int = os.environ.get("REQUEST_TIMEOUT_MS", 8000)
    PROXY_CHAIN: str = 'x-proxy-chain'
    LOOP_COUNT: str = 'x-loop-count'
    TARGET_URL: str = 'x-target-url'
    HASH_AUTH: str = os.environ.get("HashAuth", 'xxx-xxx')

    HEADERS_TO_DELETE: set = {
        'sozu-id',
        'traceparent',
        'x-amzn-trace-id',
        'cdn-loop',
        'cf-connecting-ip',
        'cf-ew-via',
        'cf-ray',
        'cf-visitor',
        'cf-worker',
        'cf-ipcountry',
        'x-forwarded-for',
        'x-forwarded-host',
        'x-real-ip',
        'forwarded',
        'client-ip',
        'x-max-bytecode-size',
        'x-min-bytecode-size',
        'x-vercel-deployment-url',
        'x-vercel-forwarded-for',
        'x-vercel-id',
        'x-vercel-internal-ingress-bucket',
        'x-vercel-internal-intra-session',
        'x-vercel-ip-as-number',
        'x-vercel-ip-city',
        'x-vercel-ip-continent',
        'x-vercel-ip-country',
        'x-vercel-ip-latitude',
        'x-vercel-ip-longitude',
        'x-vercel-ip-timezone',
        'x-vercel-ja4-digest',
        'x-vercel-proxied-for',
        'x-vercel-proxy-signature',
        "x-vercel-ip-postal-code",
        # "X-Vercel-Proxy-Signature-Ts",
        # "X-Vercel-Ip-Country-Region",
    }

    @property
    def CONFIG_TO_DELETE(self):
        return {
            self.HASH_AUTH,
            self.PROXY_CHAIN,
            self.TARGET_URL,
            self.LOOP_COUNT
        } | self.HEADERS_TO_DELETE

    class Config:
        case_sensitive = True


settings = Settings()
app = FastAPI(title="Proxy Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_http_client():
    return AsyncClient(
        timeout=Timeout(settings.REQUEST_TIMEOUT_MS / 1000),
        follow_redirects=True,
        http2=True,
        limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
    )


async def proxy_request(request: Request) -> Response:
    loop_count = int(request.headers.get(settings.LOOP_COUNT, '0'))
    encoded_proxy_chain = request.headers.get(settings.PROXY_CHAIN)

    if loop_count > settings.MAX_PROXY_DEPTH:
        raise HTTPException(
            status_code=400,
            detail=f"Proxy depth exceeds maximum limit ({settings.MAX_PROXY_DEPTH})"
        )

    proxy_chain = json.loads(base64.b64decode(encoded_proxy_chain)) if encoded_proxy_chain else []
    target_url = request.headers.get(settings.TARGET_URL)

    if proxy_chain:
        proxy_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in settings.HEADERS_TO_DELETE
        }
        proxy_headers[settings.LOOP_COUNT] = str(loop_count + 1)
        target_url = proxy_chain.pop(0)

        if proxy_chain:
            proxy_headers[settings.PROXY_CHAIN] = base64.b64encode(
                json.dumps(proxy_chain).encode()
            ).decode()
    else:
        proxy_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in settings.CONFIG_TO_DELETE
        }

    proxy_headers['host'] = urlparse(target_url).netloc

    try:
        content = await request.body()
        async with await get_http_client() as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=proxy_headers,
                content=content,
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def handle_request(request: Request, path: str):
    if settings.HASH_AUTH not in request.headers:
        return Response(status_code=444)
    return await proxy_request(request)


if __name__ == "__main__":
    import platform

    config = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
        "access_log": False,
    }
    if platform.system().lower() != "windows":
        config.update({
            "loop": "uvloop",
            "http": "httptools",
        })

    uvicorn.run(**config)
