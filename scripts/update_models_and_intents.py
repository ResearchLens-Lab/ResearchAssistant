from pathlib import Path

# Update rag/independent/models.py
models_path = Path("rag/independent/models.py")
content = models_path.read_text(encoding="utf-8")
if "TABLE_SYNTHESIS" not in content:
    content = content.replace(
        '    UNKNOWN = "UNKNOWN"',
        '    TABLE_SYNTHESIS = "TABLE_SYNTHESIS"\n'
        '    LIMITATIONS_EXTRACTION = "LIMITATIONS_EXTRACTION"\n'
        '    ALGORITHMS_EXTRACTION = "ALGORITHMS_EXTRACTION"\n'
        '    DEEP_EXPLANATION = "DEEP_EXPLANATION"\n'
        '    SIMPLIFIED_EXPLANATION = "SIMPLIFIED_EXPLANATION"\n'
        '    PRACTICAL_EXAMPLE = "PRACTICAL_EXAMPLE"\n'
        '    UNKNOWN = "UNKNOWN"'
    )
    models_path.write_text(content, encoding="utf-8")
    print("rag/independent/models.py updated with new QuestionIntents.")
else:
    print("rag/independent/models.py already has new intents.")

# Update rag/independent/retriever.py
retriever_path = Path("rag/independent/retriever.py")
r_text = retriever_path.read_text(encoding="utf-8")
r_text = r_text.replace(
    '        if not terms:\n            return [], {}',
    '        if not terms:\n            terms = ["finding", "method", "result", "conclusion", "table", "summary", "paper"]'
)
retriever_path.write_text(r_text, encoding="utf-8")
print("rag/independent/retriever.py updated with fallback terms.")
