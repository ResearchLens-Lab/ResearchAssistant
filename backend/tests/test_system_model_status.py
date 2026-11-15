import pytest

from backend.app.routes import health


@pytest.mark.asyncio
async def test_model_status_is_read_only_and_reports_generation_limits(monkeypatch):
    class FakeModel:
        def __init__(self, **kwargs):
            assert kwargs["model"] == health.rag_settings.ollama_model
        def status(self):
            return {"provider": "ollama", "model": "qwen3.5:0.8b", "runtime_available": True,
                    "model_installed": True, "model_loaded": False, "inference_active": False,
                    "state": "ready_not_loaded"}

    monkeypatch.setattr(health, "OllamaLLMClient", FakeModel)
    result = await health.system_model_status()

    assert result["state"] == "ready_not_loaded"
    assert result["download_policy"] == "manual_only"
    assert result["generation_limits"]["context_tokens"] == 4096
    assert "api_key" not in result
