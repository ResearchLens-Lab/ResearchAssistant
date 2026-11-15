from pathlib import Path

path = Path("rag/independent/answer_composer.py")
text = path.read_text(encoding="utf-8")

# 1. Update _table
target_table = """        # 2. Add or augment with top scoring sentences
        if len(rows) < 5:
            for source, sentence, score in StructuredAnswerComposer._best_sentences(analysis, sources, 20):"""

replacement_table = """        # 2. Add or augment with top scoring sentences
        if len(rows) < 5:
            sentences_pool = StructuredAnswerComposer._best_sentences(analysis, sources, 20)
            if not sentences_pool and sources:
                for s in sources:
                    for sentence in _sentences(s.text):
                        sentences_pool.append((s, sentence, 1))
            for source, sentence, score in sentences_pool:"""

text = text.replace(target_table, replacement_table)

# 2. Update _general
target_gen = """    @staticmethod
    def _general(analysis, sources):
        passages = StructuredAnswerComposer._best_sentences(analysis, sources, 10)
        if not passages:
            return StructuredAnswerComposer._not_found(analysis, "The retrieved passages do not contain an identifiable answer.")"""

replacement_gen = """    @staticmethod
    def _general(analysis, sources):
        passages = StructuredAnswerComposer._best_sentences(analysis, sources, 10)
        if not passages and sources:
            for s in sources:
                for sent in _sentences(s.text):
                    passages.append((s, sent, 1))
        if not passages:
            return StructuredAnswerComposer._not_found(analysis, "The retrieved passages do not contain an identifiable answer.")"""

text = text.replace(target_gen, replacement_gen)

path.write_text(text, encoding="utf-8")
print("rag/independent/answer_composer.py updated.")

