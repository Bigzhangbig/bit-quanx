from dekt_backend.security import build_sign_message, compute_signature, hash_body_bytes


def test_hash_body_bytes_is_stable() -> None:
    assert hash_body_bytes(b"{}").startswith("44")


def test_signature_has_expected_length() -> None:
    message = build_sign_message("1", "nonce", "GET", "/api/v1/config", hash_body_bytes(b""))
    signature = compute_signature("secret", message)
    assert len(signature) == 64
