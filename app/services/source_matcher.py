from __future__ import annotations
from app.models import Entity, Source


def match_source(entities: list[Entity], sources: list[Source]) -> tuple[Source, float]:
    """
    Scores each Source by how well its variables cover the detected entities.
    Returns the best-matching Source and a confidence score (0..1).
    """
    if not sources:
        raise ValueError("No sources available")
    if not entities:
        return sources[0], 0.0

    entity_types_found = {e.type for e in entities}
    best_source = sources[0]
    best_score = -1.0

    for source in sources:
        score = _score_source(source, entities, entity_types_found)
        if score > best_score:
            best_score = score
            best_source = source

    # Normalize confidence to 0..1
    max_possible = len(entity_types_found) * 3.0 + 10.0  # rough upper bound
    confidence = min(1.0, max(0.0, best_score / max_possible)) if max_possible > 0 else 0.0

    return best_source, confidence


def _score_source(
    source: Source,
    entities: list[Entity],
    entity_types_found: set[str],
) -> float:
    """
    Scoring:
    - +2 for each entity type that has a matching variable in the source
    - +1 bonus for each marker keyword found in entity context
    - -0.5 for each source variable with entity_types that has no matching entity
    """
    score = 0.0

    # Collect all variable entity_types from this source (flat + collection fields)
    source_entity_types: set[str] = set()
    source_markers: dict[str, list[str]] = {}  # entity_type -> markers

    for var in source.variables:
        for et in var.entity_types:
            source_entity_types.add(et)
        if var.markers:
            for et in var.entity_types:
                source_markers.setdefault(et, []).extend(var.markers)
            if not var.entity_types and var.markers:
                # Variable with markers but no entity type — use markers for general matching
                source_markers.setdefault("_general_" + var.code, []).extend(var.markers)

        # Collection fields
        for field in var.fields:
            for et in getattr(field, 'entity_types', []):
                source_entity_types.add(et)

    # Score: entity type coverage
    for et in entity_types_found:
        if et in source_entity_types:
            score += 2.0

    # Score: marker matches in entity contexts
    for entity in entities:
        ctx_lower = entity.context.lower()
        for et, markers in source_markers.items():
            if entity.type == et or et.startswith("_general_"):
                for marker in markers:
                    if marker.lower() in ctx_lower:
                        score += 0.5

    # Penalty: source variables that expect entities not found in document
    for var in source.variables:
        if var.entity_types and var.type != "collection":
            has_match = any(et in entity_types_found for et in var.entity_types)
            if not has_match:
                score -= 0.3

    # Bonus: document text marker matching (check if general markers appear)
    all_contexts = " ".join(e.context.lower() for e in entities)
    for var in source.variables:
        if not var.entity_types and var.markers:
            for marker in var.markers:
                if marker.lower() in all_contexts:
                    score += 0.3

    return score
