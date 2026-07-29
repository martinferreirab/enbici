"""Función de costo para camino mínimo con penalización por pendiente."""

MAX_GRADE = 0.25


def edge_cost(length: float, grade: float, elevation_weight: float) -> float:
    """
    Calcula el peso de una arista.

    Fórmula: ``length * (1 + elevation_weight * max(0, grade))``
    con ``grade`` acotado a 25 % para evitar artefactos de datos ruidosos.
    """
    uphill_grade = min(max(grade, 0.0), MAX_GRADE)
    return length * (1.0 + elevation_weight * uphill_grade)
