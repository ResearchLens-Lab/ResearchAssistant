import pytest
from rag.intelligence.answer_composer import reflow_text, clean_passage_text


def test_reflow_preserves_pseudocode_with_assignment_and_comment():
    pseudocode = (
        "x := 1\n"
        "y := 2\n"
        "// update pointers\n"
        "x.next := y"
    )
    result = reflow_text(pseudocode)
    assert ":=" in result
    assert "// update pointers" in result
    assert result == pseudocode


def test_reflow_preserves_tables_with_pipes_and_tabs():
    table_pipes = (
        "| Operation | Cormen Runtime | Horowitz Runtime |\n"
        "| Insertion | O(log n)       | O(log n)         |\n"
        "| Search    | O(log n)       | O(log n)         |"
    )
    assert reflow_text(table_pipes) == table_pipes

    table_tabs = (
        "Header1\t\tHeader2\n"
        "val1\t\tval2"
    )
    assert reflow_text(table_tabs) == table_tabs


def test_reflow_preserves_numbered_lists_with_three_or_more_items():
    numbered_list = (
        "1. Every node is either red or black.\n"
        "2. The root is black.\n"
        "3. Every leaf (NIL) is black."
    )
    assert reflow_text(numbered_list) == numbered_list


def test_reflow_safe_dehyphenation_and_stop_words():
    # Regular dehyphenation: "ez-" + "treme" -> "extreme"
    prose_normal = "This is an ez-\ntreme example of red-black tree balancing."
    res_normal = reflow_text(prose_normal)
    assert "extreme example" in res_normal

    # Hyphen before stop word: "state-" + "and" -> keep hyphen
    prose_stop = "We examine state-\nand decision-based algorithms."
    res_stop = reflow_text(prose_stop)
    assert "state- and decision-based" in res_stop


def test_clean_passage_and_reflow_with_real_cormen_chunk():
    # Exact test string specified in requirement
    raw = (
        "13.4 Deletion 323 13.4 Deletion Like the other basic operations on an "
        "n-node red-black tree, deletion of a node takes time O.lg n/."
    )
    cleaned = clean_passage_text(raw)
    assert cleaned == (
        "13.4 Deletion Like the other basic operations on an n-node red-black tree, "
        "deletion of a node takes time O.lg n/."
    )
    assert "323" not in cleaned
    assert cleaned.count("13.4 Deletion") == 1


def test_clean_passage_with_real_horowitz_chunk():
    horowitz_raw = (
        "1. Criteria 23 1. Criteria An algorithm is a ﬁnite set of instructions.\n"
        "It satisfies the follow-\ning criteria: finiteness and definiteness."
    )
    cleaned = clean_passage_text(horowitz_raw)
    # Check ligature normalization (fi) and hyphenation rejoining (following)
    assert "finite" in cleaned
    assert "following" in cleaned
    assert "23" not in cleaned
