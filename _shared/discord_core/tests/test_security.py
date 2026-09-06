from discord_core.security import generate_keypair, sign_payload, verify_signature


def test_valid_signature_roundtrip():
    private_key, public_key = generate_keypair()
    body = b'{"type":1}'
    signature = sign_payload(private_key, "1700000000", body)
    assert verify_signature(public_key, signature, "1700000000", body)


def test_tampered_body_is_rejected():
    private_key, public_key = generate_keypair()
    signature = sign_payload(private_key, "1700000000", b'{"type":1}')
    assert not verify_signature(public_key, signature, "1700000000", b'{"type":2}')


def test_tampered_timestamp_is_rejected():
    private_key, public_key = generate_keypair()
    signature = sign_payload(private_key, "1700000000", b"x")
    assert not verify_signature(public_key, signature, "1700000001", b"x")


def test_wrong_key_is_rejected():
    private_key, _ = generate_keypair()
    _, other_public = generate_keypair()
    signature = sign_payload(private_key, "1", b"x")
    assert not verify_signature(other_public, signature, "1", b"x")


def test_malformed_inputs_do_not_raise():
    _, public_key = generate_keypair()
    assert not verify_signature(public_key, "not-hex", "1", b"x")
    assert not verify_signature("zz", "00", "1", b"x")
    assert not verify_signature(public_key, "", "", b"")
