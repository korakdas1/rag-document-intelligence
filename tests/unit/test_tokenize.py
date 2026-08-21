from research_assistant.retrieval.tokenize import tokenize


def test_underscore_identifier_keeps_compound_and_parts() -> None:
    tokens = tokenize("ERR_CONNECTION_REFUSED")
    assert "err_connection_refused" in tokens
    assert "err" in tokens
    assert "connection" in tokens
    assert "refused" in tokens


def test_hyphenated_term_keeps_compound_and_parts() -> None:
    tokens = tokenize("transformer-based")
    assert "transformer-based" in tokens
    assert "transformer" in tokens
    assert "based" in tokens


def test_acronym_and_version() -> None:
    tokens = tokenize("BGE-small-en-v1.5")
    assert "bge-small-en-v1.5" in tokens
    assert "bge" in tokens
    assert "small" in tokens


def test_number_and_percent() -> None:
    tokens = tokenize("Recall@K dropped to 10.5%")
    assert "recall" in tokens
    assert "k" in tokens
    assert "10.5" in tokens


def test_unicode_is_normalized() -> None:
    tokens = tokenize("café naïve")
    assert "café" in tokens or "cafe" in tokens
    assert "naïve" in tokens or "naive" in tokens


def test_document_id_style_identifier() -> None:
    tokens = tokenize("chunk document_id GPT-5")
    assert "document_id" in tokens
    assert "gpt-5" in tokens
    assert "gpt" in tokens
