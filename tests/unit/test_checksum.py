from research_assistant.ingestion.checksum import sha256_bytes


def test_checksum_is_deterministic() -> None:
    payload = "café\n".encode("utf-8")
    assert sha256_bytes(payload) == sha256_bytes(payload)
    assert len(sha256_bytes(payload)) == 64


def test_checksum_changes_when_bytes_change() -> None:
    assert sha256_bytes(b"alpha") != sha256_bytes(b"beta")
