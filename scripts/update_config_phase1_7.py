from pathlib import Path

# 1. Update rag/config/settings.py
settings_path = Path("rag/config/settings.py")
content = settings_path.read_text(encoding="utf-8")
content = content.replace(
    'rag_engine_mode: Literal["legacy", "independent"] = "legacy"',
    'rag_engine_mode: Literal["legacy", "independent"] = "independent"'
)
content = content.replace(
    'rag_answer_mode: Literal["EXTRACTIVE", "LOCAL_QWEN"] = "LOCAL_QWEN"',
    'rag_answer_mode: str = "INDEPENDENT"'
)
content = content.replace(
    'llm_provider: Literal["local", "mock", "gemini", "ollama", "openai"] = "ollama"',
    'llm_provider: Literal["local", "mock", "gemini", "ollama", "openai", "none"] = "none"'
)
content = content.replace(
    'llm_model: str = "qwen3.5:0.8b"',
    'llm_model: str = "none"'
)
settings_path.write_text(content, encoding="utf-8")
print("rag/config/settings.py updated.")

# 2. Update backend/app/core/config.py
backend_config_path = Path("backend/app/core/config.py")
b_content = backend_config_path.read_text(encoding="utf-8")
if 'rag_engine_mode' not in b_content:
    b_content = b_content.replace(
        'rag_mode: str = "local"',
        'rag_mode: str = "local"\n    rag_engine_mode: str = "independent"'
    )
b_content = b_content.replace(
    'rag_answer_mode: str = "LOCAL_QWEN"',
    'rag_answer_mode: str = "INDEPENDENT"'
)
backend_config_path.write_text(b_content, encoding="utf-8")
print("backend/app/core/config.py updated.")

# 3. Update backend/app/schemas/chat.py
chat_schema_path = Path("backend/app/schemas/chat.py")
c_content = chat_schema_path.read_text(encoding="utf-8")
c_content = c_content.replace(
    'answer_mode: Literal["DOCUMENTS_GENERAL", "DOCUMENTS_ONLY"] = "DOCUMENTS_GENERAL"',
    'answer_mode: Literal["EVIDENCE_FIRST", "DOCUMENTS_GENERAL", "OPTIONAL_LOCAL_AI", "DOCUMENTS_ONLY", "INDEPENDENT"] = "EVIDENCE_FIRST"'
)
chat_schema_path.write_text(c_content, encoding="utf-8")
print("backend/app/schemas/chat.py updated.")
