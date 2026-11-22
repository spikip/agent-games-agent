"""Agent Games agent — FastAPI.

Endpoint:
  POST /agent   — terima task terenkripsi-tanda tangan (HMAC-SHA256), balas keputusan
  GET  /health  — health check untuk registrasi/dashboard

Autentikasi: header x-agent-games-signature = HMAC-SHA256(secret, raw_body) hex.
Secret dibaca dari env AGENT_GAMES_SECRET (JANGAN hardcode). Jika secret belum
di-set (dev lokal), verifikasi dilewati dengan peringatan di log — untuk
produksi/kompetisi WAJIB set secret dari dashboard (Rotate Secret).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .gatekeeper import evaluate

log = logging.getLogger("agent-games")
logging.basicConfig(level=logging.INFO)

SECRET = os.environ.get("AGENT_GAMES_SECRET", "")
if not SECRET:
    log.warning("AGENT_GAMES_SECRET not set — signature verification DISABLED (local dev only).")

app = FastAPI(title="Agent Games — Proof Gatekeeper Agent (@budikanebo)")


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest() if SECRET else ""


def _valid_signature(raw: bytes, header: str | None) -> bool:
    if not SECRET:
        return True  # dev mode
    if not header:
        return False
    given = header.removeprefix("sha256=").strip()
    return hmac.compare_digest(given, _sign(raw))


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "proof-gatekeeper", "signature_verification": bool(SECRET)}


@app.post("/agent")
async def agent(request: Request):
    raw = await request.body()
    if not _valid_signature(raw, request.headers.get("x-agent-games-signature")):
        return JSONResponse({"error": "invalid_signature"}, status_code=401)
    try:
        task = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    event_id = str(task.get("event_id") or task.get("eventId") or "")

    # --- Steal the VFY: handler minimal (HOLD aman), TIDAK mengarang proof ---
    if "steal" in event_id.lower():
        body = {
            "matchId": task.get("matchId") or task.get("match_id"),
            "turn": task.get("turn"),
            "action": {"type": "HOLD"},  # tanpa field amount (wajib diomit untuk HOLD)
            "policyProof": None,
            "note": "Minimal placeholder handler — strategy & Groth16 policy proof belum diimplementasikan.",
        }
        content = json.dumps(body).encode()
        headers = {"x-agent-games-signature": _sign(content)} if SECRET else {}
        return JSONResponse(content=body, headers=headers)

    # --- Proof Gatekeeper (default) ---
    result = evaluate(task)
    result["task_id"] = task.get("task_id")
    result["event_id"] = event_id or "proof-gatekeeper"
    content = json.dumps(result).encode()
    headers = {"x-agent-games-signature": _sign(content)} if SECRET else {}
    return JSONResponse(content=result, headers=headers)
