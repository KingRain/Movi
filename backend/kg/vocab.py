"""Relation and entity labels for the bundled music KFGAN knowledge graph."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "kfgan" / "data" / "music"


@lru_cache(maxsize=1)
def relation_labels() -> dict[int, str]:
    """Map relation index (kg_final) to Freebase-style relation name."""
    kg_path = DATA_ROOT / "kg.txt"
    relation_id2name: dict[str, int] = {}
    relation_labels: dict[int, str] = {}
    for line in kg_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 3:
            continue
        rel_name = parts[1]
        if rel_name not in relation_id2name:
            idx = len(relation_id2name)
            relation_id2name[rel_name] = idx
            relation_labels[idx] = rel_name
    return relation_labels


@lru_cache(maxsize=1)
def entity_to_item_index() -> dict[int, int]:
    """Map KG entity index to KFGAN item index (when the entity is a catalog item)."""
    mapping: dict[int, int] = {}
    path = DATA_ROOT / "item_index2entity_id.txt"
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 2:
            continue
        item_index = int(parts[0])
        entity_index = int(parts[1])
        mapping[entity_index] = item_index
    return mapping


def label_entity(entity_id: int, movie_label_fn) -> tuple[str, str]:
    """Return (label, kind) where kind is item | entity."""
    item_index = entity_to_item_index().get(entity_id)
    if item_index is not None:
        meta = movie_label_fn(item_index)
        return meta.get("title") or f"Item {item_index}", "item"
    return f"Entity {entity_id}", "entity"


def enrich_kfgan_edges(edges: list[dict], movie_label_fn) -> tuple[list[dict], list[dict]]:
    """Add human-readable fields and a node list for graph visualization."""
    rel_map = relation_labels()
    nodes: dict[str, dict] = {}

    def add_node(key: str, label: str, kind: str) -> None:
        if key not in nodes:
            nodes[key] = {"id": key, "label": label, "kind": kind}

    enriched: list[dict] = []
    for edge in edges:
        rel_id = int(edge["rel"])
        rel_name = rel_map.get(rel_id, f"relation_{rel_id}")
        from_id = int(edge["from"])
        to_id = int(edge["to"])
        from_label, from_kind = label_entity(from_id, movie_label_fn)
        to_label, to_kind = label_entity(to_id, movie_label_fn)
        from_key = f"e:{from_id}"
        to_key = f"e:{to_id}"
        add_node(from_key, from_label, from_kind)
        add_node(to_key, to_label, to_kind)
        enriched.append(
            {
                **edge,
                "rel_name": rel_name,
                "from_label": from_label,
                "to_label": to_label,
            }
        )

    return enriched, list(nodes.values())
