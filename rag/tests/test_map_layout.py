import pytest
from rag.intelligence.map_layout import compute_map_layout, MapNode


def count_collisions(nodes: list[MapNode]) -> int:
    collisions = 0
    n = len(nodes)
    for i in range(n):
        for j in range(i + 1, n):
            if nodes[i].intersects(nodes[j]):
                collisions += 1
    return collisions


def test_one_turn_root_at_center():
    width = 1200.0
    height = 800.0
    turns = [{"id": "t1", "question": "What is a red-black tree?"}]
    layout = compute_map_layout(turns, width=width, height=height)

    root = layout["root"]
    assert root.x == width / 2.0
    assert root.y == height / 2.0
    assert len(layout["nodes"]) == 2
    assert count_collisions(layout["nodes"]) == 0


def test_four_turns_no_collisions():
    width = 1200.0
    height = 800.0
    turns = [
        {"id": "t1", "question": "Red-Black Tree Definition"},
        {"id": "t2", "question": "Insertion Complexity"},
        {"id": "t3", "question": "Deletion Procedure"},
        {"id": "t4", "question": "Rotations Properties"},
    ]
    layout = compute_map_layout(turns, width=width, height=height)

    root = layout["root"]
    assert root.x == width / 2.0
    assert root.y == height / 2.0
    assert len(layout["nodes"]) == 5  # root + 4 children

    # Verify no bounding box collisions
    collisions = count_collisions(layout["nodes"])
    assert collisions == 0, f"Expected 0 collisions among 4 turns + root, found {collisions}"


def test_twelve_turns_across_two_branches():
    width = 3000.0
    height = 1000.0
    turns = [
        {"id": f"t{i}", "question": f"Question {i}", "branch_id": "branch_1" if i <= 6 else "branch_2"}
        for i in range(1, 13)
    ]
    layout = compute_map_layout(turns, width=width, height=height)

    nodes = layout["nodes"]
    assert len(nodes) == 1 + 2 + 12  # root + 2 branches + 12 turns

    # 1. 0 collisions across all nodes
    collisions = count_collisions(nodes)
    assert collisions == 0, f"Expected 0 collisions, found {collisions}"

    # 2. Horizontal separation >= 200 between sibling turns
    b1_turns = [n for n in nodes if n.parent_id == "branch_1"]
    b2_turns = [n for n in nodes if n.parent_id == "branch_2"]
    assert len(b1_turns) == 6
    assert len(b2_turns) == 6

    for branch_turns in (b1_turns, b2_turns):
        sorted_turns = sorted(branch_turns, key=lambda n: n.x)
        for i in range(len(sorted_turns) - 1):
            h_sep = sorted_turns[i + 1].x - sorted_turns[i].x
            assert h_sep >= 200.0, f"Horizontal separation {h_sep} is less than 200.0"

    # 3. Vertical separation >= 80 between levels
    root = layout["root"]
    branch_nodes = [n for n in nodes if n.node_type == "branch"]
    for b in branch_nodes:
        v_sep_root_branch = b.y - root.y
        assert v_sep_root_branch >= 80.0, f"Vertical separation {v_sep_root_branch} < 80.0"

    for t in b1_turns + b2_turns:
        parent = next(b for b in branch_nodes if b.id == t.parent_id)
        v_sep_branch_turn = t.y - parent.y
        assert v_sep_branch_turn >= 80.0, f"Vertical separation {v_sep_branch_turn} < 80.0"
