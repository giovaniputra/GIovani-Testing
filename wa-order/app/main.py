"""Langkah 1 - Gerbang WhatsApp: webhook Cloud API + endpoint simulasi untuk demo/uji."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import service, store


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init_db()
    yield


app = FastAPI(title="WA Order Intake", lifespan=lifespan)
STATIC = Path(__file__).parent.parent / "static"


def _production() -> bool:
    return os.environ.get("APP_ENV") == "production"


def _debug_only() -> None:
    """Endpoint simulasi/inspeksi hanya untuk lokal. Di production tampil 404."""
    if _production():
        raise HTTPException(404, "Not Found")


def _valid_signature(body: bytes, header: str | None) -> bool:
    secret = os.environ.get("WHATSAPP_APP_SECRET")
    if not secret:  # dev: tidak dicek. production: tanpa secret semua webhook ditolak
        return not _production()
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


@app.get("/webhook")
def verify(request: Request):
    q = request.query_params
    token = os.environ.get("WHATSAPP_VERIFY_TOKEN") or (None if _production() else "dev-verify-token")
    if token and q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == token:
        return Response(q.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403, "verify token salah")


@app.post("/webhook")
async def receive(request: Request):
    body = await request.body()
    if not _valid_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403, "signature tidak valid")
    payload = json.loads(body or b"{}")
    results = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                mtype = msg.get("type", "text")
                text = msg.get("text", {}).get("body") if mtype == "text" else None
                results.append(service.handle_incoming(msg["from"], text, msg.get("id"), mtype))
    return {"processed": len(results)}  # WA hanya butuh 200 cepat


class Sim(BaseModel):
    phone: str
    text: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/simulate")
def simulate(m: Sim):
    _debug_only()
    return service.handle_incoming(m.phone, m.text)


@app.get("/api/orders")
def orders():
    _debug_only()
    return store.list_orders()


@app.get("/api/outbox")
def outbox(phone: str | None = None):
    _debug_only()
    return store.list_outbox(phone)


@app.get("/")
def index():
    _debug_only()
    return FileResponse(STATIC / "index.html")
