from __future__ import annotations
from app.models import Entity, Source, Variable, MappingEntry, UnmappedEntry


def map_entities_to_variables(
    entities: list[Entity],
    source: Source,
) -> tuple[list[MappingEntry], list[UnmappedEntry]]:
    """
    Maps detected entities to the best-matching variables of the given Source.
    Returns (mappings, unmapped) where mappings only include dynamic variables.
    """
    mappings: list[MappingEntry] = []
    unmapped: list[UnmappedEntry] = []

    # Build a lookup: entity_type -> list of candidate variables
    type_to_vars: dict[str, list[Variable]] = {}
    for var in source.variables:
        if var.type == "collection":
            continue  # skip collections for MVP
        for et in var.entity_types:
            type_to_vars.setdefault(et, []).append(var)

    # Track which variables have been assigned (to avoid duplicates)
    assigned_vars: dict[str, MappingEntry] = {}  # var.code -> mapping

    # Sort entities by position to process in document order
    sorted_entities = sorted(entities, key=lambda e: e.start)

    for entity in sorted_entities:
        candidate_vars = type_to_vars.get(entity.type, [])

        if not candidate_vars:
            # No matching variable type in this source
            unmapped.append(UnmappedEntry(
                original=entity.text,
                entity_type=entity.type,
                reason=f"Нет переменной типа {entity.type} в источнике «{source.name}»",
                context=entity.context,
            ))
            continue

        # Score each candidate variable by marker match in context
        best_var = None
        best_score = -1.0

        for var in candidate_vars:
            score = _score_variable_match(entity, var)
            # If this var is already assigned, slightly penalize re-assignment
            if var.code in assigned_vars:
                score -= 0.5
            if score > best_score:
                best_score = score
                best_var = var

        if best_var is None:
            unmapped.append(UnmappedEntry(
                original=entity.text,
                entity_type=entity.type,
                reason="Не удалось сопоставить с переменной",
                context=entity.context,
            ))
            continue

        mapping = MappingEntry(
            original=entity.text,
            variable=best_var.code,
            variable_label=best_var.label,
            context=entity.context,
            dynamic=best_var.dynamic,
            confidence=best_score,
        )

        # If variable already assigned, check if this is a repeat of the same value
        if best_var.code in assigned_vars:
            existing = assigned_vars[best_var.code]
            if existing.original == entity.text:
                # Same value appearing again — still add mapping for replacement
                mappings.append(mapping)
                continue
            else:
                # Different value for same variable — check if there's another var
                # Try to find an alternative variable
                alt_found = False
                for var in candidate_vars:
                    if var.code not in assigned_vars or assigned_vars[var.code].original == entity.text:
                        alt_score = _score_variable_match(entity, var)
                        if alt_score > 0:
                            mapping = MappingEntry(
                                original=entity.text,
                                variable=var.code,
                                variable_label=var.label,
                                context=entity.context,
                                dynamic=var.dynamic,
                                confidence=alt_score,
                            )
                            assigned_vars[var.code] = mapping
                            mappings.append(mapping)
                            alt_found = True
                            break
                if not alt_found:
                    # Add as additional mapping for the same variable
                    mappings.append(mapping)
                continue

        assigned_vars[best_var.code] = mapping
        mappings.append(mapping)

    return mappings, unmapped


def _score_variable_match(entity: Entity, var: Variable) -> float:
    """Score how well an entity matches a specific variable based on markers and context."""
    score = 1.0  # base score for type match
    ctx_lower = entity.context.lower()

    for marker in var.markers:
        if marker.lower() in ctx_lower:
            score += 2.0

    # Bonus for entity type exact match
    if entity.type in var.entity_types:
        score += 0.5

    return score


def filter_dynamic_mappings(
    mappings: list[MappingEntry],
) -> tuple[list[MappingEntry], list[MappingEntry]]:
    """
    Splits mappings into:
    - dynamic_mappings: will be replaced with MERGEFIELD
    - static_mappings: will be left as-is in the document
    """
    dynamic = [m for m in mappings if m.dynamic]
    static = [m for m in mappings if not m.dynamic]
    return dynamic, static
