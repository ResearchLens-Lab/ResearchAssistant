import os
import socket
import pytest
from rag.intelligence.engine import ResearchIntelligenceEngine


class NetworkAttemptError(RuntimeError):
    pass


def test_offline_zero_network_calls(monkeypatch):
    """Verifies that the RAG intelligence engine makes ZERO outbound network calls."""
    db_path = os.path.join(os.environ.get("TEMP", ""), "rl_diag_copy", "researchlens_lexical.sqlite3")
    if not os.path.exists(db_path):
        pytest.skip("Test requires %TEMP%\\rl_diag_copy\\researchlens_lexical.sqlite3")

    network_attempts = []

    def mock_connect(self, address):
        network_attempts.append(address)
        raise NetworkAttemptError(f"Prohibited network connection attempted: {address}")

    def mock_getaddrinfo(*args, **kwargs):
        network_attempts.append(args)
        raise NetworkAttemptError(f"Prohibited DNS resolution attempted: {args}")

    monkeypatch.setattr(socket.socket, "connect", mock_connect)
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    engine = ResearchIntelligenceEngine(db_path=db_path)
    result = engine.answer_query("Explain binary search algorithms")

    assert len(network_attempts) == 0, f"Expected 0 network calls, but got: {network_attempts}"
    assert result is not None
    assert result.markdown_content is not None
    assert len(result.markdown_content) > 0
    assert result.cited_sources is not None
    assert len(result.cited_sources) > 0
