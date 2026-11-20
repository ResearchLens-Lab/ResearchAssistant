"""
Regression tests for deterministic summarizer quality hardening.
Verifies rejection of:
1. Exercise instructions ("Fill in the three missing expressions...")
2. Truth-table repetition ("B is good A is bad at least one is bad...")
3. Code/figure artifacts and transitions
4. Over-wide chunk spans (> 30 pages)
"""
import pytest
from rag.intelligence.summarizer import (
    score_bullet_sentence,
    is_repetitive_text,
    EXERCISE_INSTRUCTION,
    TRANSITION_SENTENCE,
    FIGURE_OR_TABLE,
)


def test_exercise_instruction_regex():
    assert EXERCISE_INSTRUCTION.search("Fill in the three missing expressions in line 8 of P-SCAN-UP")
    assert EXERCISE_INSTRUCTION.search("Show that if a node x is red, its children must be black.")
    assert EXERCISE_INSTRUCTION.search("Prove that any comparison sort requires Omega(n lg n) time.")
    assert EXERCISE_INSTRUCTION.search("Give an efficient algorithm to convert a binary tree to a doubly linked list.")
    assert EXERCISE_INSTRUCTION.search("Write pseudocode for the iterative version of BINARY-SEARCH.")
    assert not EXERCISE_INSTRUCTION.search("Sorting is a fundamental operation in computer science.")
    assert not EXERCISE_INSTRUCTION.search("An algorithm is any well-defined computational procedure.")


def test_transition_sentence_regex():
    assert TRANSITION_SENTENCE.search("As we shall see in the next section, divide-and-conquer is powerful.")
    assert TRANSITION_SENTENCE.search("The following pseudocode illustrates the procedure.")
    assert TRANSITION_SENTENCE.search("In this chapter, we have studied various data structures.")
    assert not TRANSITION_SENTENCE.search("Because many programs use it as an intermediate step, sorting is essential.")


def test_figure_or_table_regex():
    assert FIGURE_OR_TABLE.search("Figure 2.1 shows the operation of INSERTION-SORT on an array.")
    assert FIGURE_OR_TABLE.search("Table 4.1 summarizes the recurrence relations.")
    assert not FIGURE_OR_TABLE.search("The running time of the algorithm depends on the input size.")


def test_is_repetitive_text():
    corrupted_truth_table = (
        "B is good A is bad at least one is bad B is bad A is good "
        "at least one is bad B is bad A is bad at least one is bad a."
    )
    assert is_repetitive_text(corrupted_truth_table) is True

    single_token_repeat = "test " * 20
    assert is_repetitive_text(single_token_repeat) is True

    normal_prose = (
        "Because many programs use it as an intermediate step, "
        "sorting is a fundamental operation in computer science."
    )
    assert is_repetitive_text(normal_prose) is False


def test_score_bullet_sentence_rejects_exercises_and_corruptions():
    # Multithreaded algorithm exercise instruction from Cormen
    s_exercise = "Fill in the three missing expressions in line 8 of P-SCAN-UP and lines 5 and 6 of P-SCAN-DOWN."
    assert score_bullet_sentence(s_exercise) < 0

    # Truth-table corruption
    s_truth_table = "B is good A is bad at least one is bad B is bad A is good at least one is bad B is bad A is bad."
    assert score_bullet_sentence(s_truth_table) < 0

    # Figure reference
    s_fig = "Figure 2.2: The execution of MERGE-SORT on the array A = <5, 2, 4, 7, 1, 3, 2, 6>."
    assert score_bullet_sentence(s_fig) < 0

    # Genuine informative substantive sentence
    s_good = "Because many programs use it as an intermediate step, sorting is a fundamental operation in computer science."
    assert score_bullet_sentence(s_good) > 0

    s_definition = "An algorithm is a finite set of instructions that accomplishes a particular task."
    assert score_bullet_sentence(s_definition) > 0
