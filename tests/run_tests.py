"""Tes lokal: jalankan agent (in-process via TestClient), kirim contoh payload,
tulis hasil ke TEST_RESULTS.md. Pakai: ../.venv/bin/python tests/run_tests.py
(dari folder agent/, dengan venv yang berisi fastapi+httpx)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    ("valid_task.json", "approve", "VALID_PROOF"),
    ("invalid_vk_task.json", "reject", "VK_SUBSTITUTION"),
]

client = TestClient(app)
lines = ["# Hasil Tes Lokal — Proof Gatekeeper Agent", ""]
all_pass = True
for fname, exp_decision, exp_reason in CASES:
    payload = json.loads((ROOT / "examples" / fname).read_text())
    r = client.post("/agent", json=payload)
    body = r.json()
    ok = r.status_code == 200 and body.get("decision") == exp_decision and body.get("reason_code") == exp_reason
    all_pass &= ok
    lines += [
        f"## {fname}",
        f"- HTTP status: {r.status_code}",
        f"- Expected: decision={exp_decision}, reason_code={exp_reason}",
        f"- Got: decision={body.get('decision')}, reason_code={body.get('reason_code')}",
        f"- Status: {'LULUS ✅' if ok else 'GAGAL ❌'}",
        "- Response:",
        "```json",
        json.dumps(body, indent=2),
        "```",
        "",
    ]
lines.append(f"**Semua tes lulus: {all_pass}**")
(ROOT / "TEST_RESULTS.md").write_text("\n".join(lines))
print("\n".join(lines))
sys.exit(0 if all_pass else 1)
