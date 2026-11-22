# Hasil Tes Lokal — Proof Gatekeeper Agent

## valid_task.json
- HTTP status: 200
- Expected: decision=approve, reason_code=VALID_PROOF
- Got: decision=approve, reason_code=VALID_PROOF
- Status: LULUS ✅
- Response:
```json
{
  "decision": "approve",
  "reason_code": "VALID_PROOF",
  "proof_check": {
    "verified": true,
    "proof_valid": true,
    "vk_match": true,
    "public_input_match": true,
    "replay_check": true
  },
  "verification_method": "zkverify-relayer",
  "verification_details": {
    "local_checks": [
      "completeness",
      "verified_flag",
      "vk_match",
      "circuit_supported",
      "public_input_match",
      "threshold",
      "replay_seen_set"
    ],
    "cryptographic_reverification": "not_performed_locally (see README limitations)"
  },
  "evidence": [
    "All required verification fields present.",
    "verification_result.verified == true (platform-reported).",
    "proof_vk matches registered_vk.",
    "Proof system groth16-bn254 is supported (circuit_id=payment_transfer_v1).",
    "Public inputs (amount/recipient/nonce) match the payment request.",
    "amount 12.5 >= required_threshold 10.0.",
    "No replay detected (tx_ref/nonce/proof fingerprint is new)."
  ],
  "confidence": 0.95,
  "timeout": false,
  "task_id": "pgk-2026-11-13-0001",
  "event_id": "proof-gatekeeper"
}
```

## invalid_vk_task.json
- HTTP status: 200
- Expected: decision=reject, reason_code=VK_SUBSTITUTION
- Got: decision=reject, reason_code=VK_SUBSTITUTION
- Status: LULUS ✅
- Response:
```json
{
  "decision": "reject",
  "reason_code": "VK_SUBSTITUTION",
  "proof_check": {
    "verified": true,
    "proof_valid": true,
    "vk_match": false,
    "public_input_match": false,
    "replay_check": true
  },
  "verification_method": "zkverify-relayer",
  "verification_details": {
    "local_checks": [
      "completeness",
      "verified_flag",
      "vk_match",
      "circuit_supported",
      "public_input_match",
      "threshold",
      "replay_seen_set"
    ],
    "cryptographic_reverification": "not_performed_locally (see README limitations)"
  },
  "evidence": [
    "All required verification fields present.",
    "verification_result.verified == true (platform-reported).",
    "proof_vk 0xDEAD00000000000000000000000000000000000000000000000000000000beef != registered_vk 0x4f2a000000000000000000000000000000000000000000000000000000000001."
  ],
  "confidence": 0.95,
  "timeout": false,
  "task_id": "pgk-2026-11-13-0002-trap",
  "event_id": "proof-gatekeeper"
}
```

**Semua tes lulus: True**

## Tes server live (uvicorn, AGENT_GAMES_SECRET di-set)
- GET /health -> {"status":"ok", signature_verification:true}
- POST /agent dengan HMAC valid (payload valid_task.json) -> approve / VALID_PROOF
- POST /agent tanpa signature saat secret aktif -> HTTP 401
- Status: LULUS ✅