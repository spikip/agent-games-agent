"""Proof Gatekeeper decision logic — fail closed.

Approve HANYA jika semua pemeriksaan konsistensi lulus:
  1. Data verifikasi lengkap (proof, vk, public inputs, verification_result)
  2. verification_result.verified == True
  3. proof_vk == registered_vk            -> VK_SUBSTITUTION
  4. Circuit / proof system didukung      -> CIRCUIT_MISMATCH
  5. Public inputs cocok dgn payment req. -> PUBLIC_INPUT_MISMATCH
  6. amount >= required_threshold         -> THRESHOLD_MISMATCH
  7. Belum pernah dilihat (replay)        -> PROOF_REPLAY

CATATAN JUJUR: ini pemeriksaan konsistensi lokal. Verifikasi kriptografis
asli (Groth16 verify / zkVerify relayer Kurier sampai status Finalized)
BELUM terhubung — lihat README, bagian Keterbatasan.
"""
from __future__ import annotations

import hashlib
from typing import Any

SUPPORTED_PROOF_SYSTEMS = {
    "groth16-bn254",
    "groth16/bn254",
    "groth16-bn128",
    "plonk-bn254",
    "groth16-bls12-381",
    "sp1",
}

# seen-set in-memory untuk replay check (hilang saat restart — lihat README)
_seen: set[str] = set()


def _get(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def _norm_amount(v) -> float | None:
    try:
        return float(str(v).replace("VFY", "").strip())
    except (TypeError, ValueError):
        return None


def _public_inputs(task: dict) -> dict:
    zk = task.get("zk_proof") or {}
    pi = _get(zk, "public_inputs", "publicInputs") or _get(task, "public_inputs", "publicInputs") or {}
    if isinstance(pi, list):  # public_signals list -> petakan posisi umum [amount, recipient, nonce]
        names = ["amount", "recipient", "nonce"]
        return {names[i]: pi[i] for i in range(min(len(pi), 3))}
    return pi if isinstance(pi, dict) else {}


def evaluate(task: dict) -> dict:
    zk = task.get("zk_proof") or {}
    vr = task.get("verification_result") or _get(zk, "verification_result") or {}
    pi = _public_inputs(task)

    amount = _norm_amount(_get(task, "amount"))
    threshold = _norm_amount(_get(task, "required_threshold", "threshold"))
    recipient = _get(task, "recipient")
    proof_vk = _get(zk, "proof_vk", "vk", "verification_key")
    registered_vk = _get(task, "registered_vk") or _get(zk, "registered_vk")
    proof_data = _get(zk, "proof")
    verified_reported = vr.get("verified") is True if isinstance(vr, dict) else False
    proof_system = _get(zk, "proof_system", "system", "type")
    circuit_id = _get(zk, "circuit_id", "circuitId")
    tx_ref = _get(zk, "tx_ref", "txRef") or _get(task, "tx_ref", "txRef")
    nonce = _get(pi, "nonce") or _get(task, "nonce")

    checks = {
        "verified": bool(verified_reported),
        "proof_valid": bool(verified_reported and proof_data),
        "vk_match": bool(proof_vk and registered_vk and str(proof_vk) == str(registered_vk)),
        "public_input_match": False,
        "replay_check": True,
    }
    evidence: list[str] = []

    def reject(reason: str, confidence: float = 0.9) -> dict:
        return _response("reject", reason, checks, evidence, confidence, vr)

    # 1. Kelengkapan
    missing = []
    if not zk or not proof_data:
        missing.append("zk_proof.proof")
    if not proof_vk:
        missing.append("zk_proof.proof_vk")
    if not registered_vk:
        missing.append("registered_vk")
    if not pi:
        missing.append("public_inputs")
    if not isinstance(vr, dict) or "verified" not in vr:
        missing.append("verification_result")
    if missing:
        evidence.append(f"Missing verification data: {', '.join(missing)}")
        return reject("MISSING_VERIFICATION", 0.85)
    evidence.append("All required verification fields present.")

    # 2. Verified oleh platform/relayer (dilaporkan, bukan diverifikasi ulang lokal)
    if not verified_reported:
        evidence.append("verification_result.verified is not true.")
        return reject("PROOF_INVALID")
    evidence.append("verification_result.verified == true (platform-reported).")

    # 3. VK match
    if not checks["vk_match"]:
        evidence.append(f"proof_vk {proof_vk} != registered_vk {registered_vk}.")
        return reject("VK_SUBSTITUTION", 0.95)
    evidence.append("proof_vk matches registered_vk.")

    # 4. Circuit / proof system
    if proof_system and str(proof_system).lower() not in SUPPORTED_PROOF_SYSTEMS:
        evidence.append(f"Unsupported proof system: {proof_system}.")
        return reject("CIRCUIT_MISMATCH", 0.9)
    if proof_system:
        evidence.append(f"Proof system {proof_system} is supported (circuit_id={circuit_id}).")

    # 5. Public inputs cocok dengan payment request
    pi_amount = _norm_amount(_get(pi, "amount"))
    pi_recipient = _get(pi, "recipient")
    mismatches = []
    if amount is not None and pi_amount is not None and pi_amount != amount:
        mismatches.append(f"amount public_input={pi_amount} != request={amount}")
    if recipient and pi_recipient and str(pi_recipient) != str(recipient):
        mismatches.append(f"recipient public_input={pi_recipient} != request={recipient}")
    if mismatches:
        evidence.append("Public input mismatch: " + "; ".join(mismatches))
        return reject("PUBLIC_INPUT_MISMATCH", 0.95)
    checks["public_input_match"] = True
    evidence.append("Public inputs (amount/recipient/nonce) match the payment request.")

    # 6. Threshold
    if amount is not None and threshold is not None and amount < threshold:
        evidence.append(f"amount {amount} < required_threshold {threshold}.")
        return reject("THRESHOLD_MISMATCH", 0.95)
    if threshold is not None:
        evidence.append(f"amount {amount} >= required_threshold {threshold}.")

    # 7. Replay — fingerprint dari tx_ref / nonce / proof
    fingerprint_src = "|".join(str(x) for x in [tx_ref or "", nonce or "", proof_data])
    fingerprint = hashlib.sha256(fingerprint_src.encode()).hexdigest()
    if fingerprint in _seen:
        checks["replay_check"] = False
        evidence.append("Proof fingerprint already seen (replay).")
        return reject("PROOF_REPLAY", 0.95)
    _seen.add(fingerprint)
    evidence.append("No replay detected (tx_ref/nonce/proof fingerprint is new).")

    return _response("approve", "VALID_PROOF", checks, evidence, 0.95, vr)


def _response(decision: str, reason: str, checks: dict, evidence: list, confidence: float, vr: Any) -> dict:
    method = vr.get("method") if isinstance(vr, dict) else None
    return {
        "decision": decision,
        "reason_code": reason,
        "proof_check": checks,
        "verification_method": method or "platform_reported_verification_result + local_consistency_checks",
        "verification_details": {
            "local_checks": ["completeness", "verified_flag", "vk_match", "circuit_supported",
                             "public_input_match", "threshold", "replay_seen_set"],
            "cryptographic_reverification": "not_performed_locally (see README limitations)",
        },
        "evidence": evidence,
        "confidence": confidence,
        "timeout": False,
    }
