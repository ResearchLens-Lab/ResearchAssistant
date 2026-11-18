import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MapNode:
    id: str
    label: str
    x: float
    y: float
    width: float = 160.0
    height: float = 40.0
    node_type: str = "turn"
    parent_id: Optional[str] = None

    def intersects(self, other: "MapNode") -> bool:
        return (
            abs(self.x - other.x) < (self.width + other.width) / 2.0
            and abs(self.y - other.y) < (self.height + other.height) / 2.0
        )


def compute_map_layout(
    turns: List[Dict[str, Any]],
    width: float = 1200.0,
    height: float = 800.0,
    root_title: str = "Research Session",
) -> Dict[str, Any]:
    """
    Pure layout function for ResearchLens mind map / research graph:
    - 1 turn: root positioned at canvas center.
    - 4 turns: root with children, guaranteed 0 bounding box collisions.
    - 12 turns across 2 branches: tree layout with horizontal sep >= 200, vertical sep >= 80, 0 collisions.
    """
    center_x = width / 2.0
    center_y = height / 2.0

    count = len(turns)
    if count == 0:
        root = MapNode(id="root", label=root_title, x=center_x, y=center_y, node_type="root")
        return {"root": root, "nodes": [root], "edges": []}

    if count == 1:
        root = MapNode(id="root", label=root_title, x=center_x, y=center_y, node_type="root")
        turn_node = MapNode(
            id=str(turns[0].get("id", "turn_1")),
            label=str(turns[0].get("question", "Turn 1")),
            x=center_x,
            y=center_y + 160.0,
            parent_id="root",
        )
        return {
            "root": root,
            "nodes": [root, turn_node],
            "edges": [("root", turn_node.id)],
        }

    if count <= 4:
        root = MapNode(id="root", label=root_title, x=center_x, y=center_y, node_type="root")
        angles = [-math.pi / 2, 0, math.pi / 2, math.pi] if count == 4 else [
            -math.pi / 2 + (2 * math.pi * i) / count for i in range(count)
        ]
        nodes = [root]
        edges = []
        radius_x = 260.0
        radius_y = 180.0
        for i, turn in enumerate(turns):
            tid = str(turn.get("id", f"turn_{i+1}"))
            label = str(turn.get("question", f"Question {i+1}"))
            ang = angles[i]
            nx = center_x + math.cos(ang) * radius_x
            ny = center_y + math.sin(ang) * radius_y
            node = MapNode(id=tid, label=label, x=nx, y=ny, parent_id="root")
            nodes.append(node)
            edges.append(("root", tid))
        return {"root": root, "nodes": nodes, "edges": edges}

    # Count > 4 (e.g. 12 turns across 2 branches) -> Hierarchical tree layout
    root = MapNode(id="root", label=root_title, x=center_x, y=100.0, node_type="root")
    branch_map: Dict[str, List[Dict[str, Any]]] = {}
    for idx, turn in enumerate(turns):
        b_id = turn.get("branch_id")
        if not b_id:
            b_id = "branch_1" if idx < count // 2 else "branch_2"
        branch_map.setdefault(b_id, []).append(turn)

    branch_list = list(branch_map.keys())
    num_branches = len(branch_list)
    v_gap_level1 = 120.0
    v_gap_level2 = 120.0
    leaf_h_sep = 220.0  # Horizontal separation >= 200

    branch_widths = [len(branch_map[b]) * leaf_h_sep for b in branch_list]
    total_width = sum(branch_widths) + (num_branches - 1) * 100.0
    start_x = center_x - total_width / 2.0
    curr_x = start_x

    nodes = [root]
    edges = []

    for b_idx, b_id in enumerate(branch_list):
        b_turns = branch_map[b_id]
        b_width = len(b_turns) * leaf_h_sep
        b_center_x = curr_x + b_width / 2.0
        b_y = root.y + v_gap_level1

        b_node = MapNode(
            id=b_id,
            label=f"Branch {b_idx + 1}",
            x=b_center_x,
            y=b_y,
            node_type="branch",
            parent_id="root",
        )
        nodes.append(b_node)
        edges.append(("root", b_id))

        for t_idx, turn in enumerate(b_turns):
            tx = curr_x + (t_idx + 0.5) * leaf_h_sep
            ty = b_y + v_gap_level2
            tid = str(turn.get("id", f"{b_id}_turn_{t_idx+1}"))
            label = str(turn.get("question", f"Turn {t_idx+1}"))
            t_node = MapNode(
                id=tid,
                label=label,
                x=tx,
                y=ty,
                node_type="turn",
                parent_id=b_id,
            )
            nodes.append(t_node)
            edges.append((b_id, tid))

        curr_x += b_width + 100.0

    return {"root": root, "nodes": nodes, "edges": edges}
