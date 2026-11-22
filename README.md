# Proof Gatekeeper Agent — Agent Games zkVerify

Agent untuk **Event 01 Proof Gatekeeper** (akun Agent Games **@budikanebo**, GitHub **@spikip**),
disiapkan saat Season 1 sudah tutup (registrasi agent ditutup 21 Nov 2026 22:00 UTC) agar siap
deploy & daftar begitu pendaftaran dibuka lagi / season berikutnya.

> **Catatan starter kit:** repo resmi yang disebut dokumentasi, `github.com/zkverify/agent-games-starter-kit`,
> saat dicek 22 Nov 2026 mengembalikan **404 / tidak publik** (dicek via GitHub API & halaman
> https://agentgames.zkverify.io/build). Karena itu kerangka ini dibangun mengikuti kontrak resmi
> di Playbook *Build an agent* (POST /agent, HMAC-SHA256, format respons Gatekeeper), memakai
> stack yang direkomendasikan Playbook: **Python 3.11+ + FastAPI**.

## Cara kerja (fail closed — approve hanya jika SEMUA cocok)

`POST /agent` menerima task Proof Gatekeeper, lalu memeriksa berurutan:
kelengkapan data → `verification_result.verified == true` → `proof_vk == registered_vk` →
circuit/proof system didukung (groth16-bn254, plonk-bn254, groth16-bls12-381, sp1) →
public inputs (amount/recipient/nonce) cocok dengan payment request →
`amount >= required_threshold` → belum pernah dilihat (replay, in-memory seen-set
fingerprint tx_ref+nonce+proof).

Respons selalu berisi: `decision` (approve/reject), `reason_code` canonical
(VALID_PROOF, PROOF_INVALID, THRESHOLD_MISMATCH, PROOF_REPLAY, CIRCUIT_MISMATCH,
VK_SUBSTITUTION, PUBLIC_INPUT_MISMATCH, MISSING_VERIFICATION), `proof_check`
{verified, proof_valid, vk_match, public_input_match, replay_check},
`verification_method`, `verification_details`, `evidence`, `confidence` 0–1, `timeout: false`.

Event **Steal the VFY**: ada handler minimal yang membalas HOLD tanpa field amount dan
tanpa mengarang policy proof — strategi & Groth16 policy proof **belum** diimplementasikan.

## Jalanin lokal

```bash
cd agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # isi AGENT_GAMES_SECRET (untuk lokal boleh dikosongkan = dev mode tanpa verifikasi signature)
.venv/bin/uvicorn app.main:app --port 8000
# endpoint: POST http://localhost:8000/agent   |   health: GET http://localhost:8000/health
```

Env vars:
- `AGENT_GAMES_SECRET` — secret HMAC dari dashboard Agent Games (*Rotate Secret*). **Wajib** di produksi.
  Header yang diverifikasi/dikirim: `x-agent-games-signature` = HMAC-SHA256(secret, raw body) hex.
- `PORT` — port server (default platform deploy biasanya menyetel sendiri).

## Tes

```bash
.venv/bin/python tests/run_tests.py   # menulis TEST_RESULTS.md
```
Contoh payload ada di `examples/`: `valid_task.json` (harus approve/VALID_PROOF) dan
`invalid_vk_task.json` (trap VK tidak cocok, harus reject/VK_SUBSTITUTION). Hasil terakhir: lihat `TEST_RESULTS.md`.

## Deploy (langkah umum — BELUM dilakukan)

- **Fly.io:** `fly launch` (runtime Python), set secret `fly secrets set AGENT_GAMES_SECRET=...`, deploy, catat URL HTTPS.
- **Render:** New Web Service dari repo GitHub, build `pip install -r requirements.txt`,
  start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, set env `AGENT_GAMES_SECRET`.
- **Railway:** Deploy from GitHub repo, set variable `AGENT_GAMES_SECRET`, generate domain publik.
- Setelah live: cek `GET https://<endpoint>/health` = `{"status":"ok"}`, lalu daftarkan endpoint `https://<endpoint>/agent`.

## Data yang dibutuhkan saat pendaftaran Agent Games dibuka lagi

- **Nama agent publik** (identifier di leaderboard, mis. nama unik pilihanmu — belum ditentukan)
- **Repo publik** di akun personal **github.com/spikip** (repo organization tidak didukung platform) — push folder ini ke sana
- **Endpoint HTTPS publik**: `https://<host>/agent`
- **Track:** Proof Gatekeeper (Steal the VFY opsional, handler-nya masih minimal)
- **API secret** dari dashboard (Rotate Secret) → set sebagai `AGENT_GAMES_SECRET` di platform deploy
- Wallet terkonfirmasi hanya dibutuhkan nanti untuk klaim hadiah VFY

## Keterbatasan (jujur)

- **Verifikasi zkVerify asli BELUM terhubung:** agent ini percaya flag `verification_result.verified`
  dari platform + melakukan pemeriksaan konsistensi lokal. Belum ada verifikasi kriptografis Groth16
  sendiri, belum submit/polling proof ke relayer **Kurier** sampai status *Finalized*, dan belum
  generate proof keputusan (snarkjs + circuit artifacts `gatekeeper.wasm`/`.zkey` dari `/api/circuit-info`).
  Itu langkah wajib berikutnya sebelum benar-benar kompetitif.
- Replay seen-set masih **in-memory** (hilang saat restart) — produksi perlu storage persisten (KV/DB).
- Target performa Gatekeeper <500 ms belum di-benchmark di hosting publik (lokal jauh di bawah itu).
