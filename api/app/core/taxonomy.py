"""ML class names ("category.type") -> catalogue fields. Mirrors ml/configs/taxonomy_pt.yaml.

Attributes known per class (keys can be missing while ML can't read them yet):
    sign.speed_limit  {"limit": 50}   speed in km/h, read from the sign (phase 2)
"""

from app.models.element import ElementCategory

LABELS: dict[str, str] = {
    "sign.stop": "Stop",
    "sign.yield": "Cedência de passagem",
    "sign.speed_limit": "Limite de velocidade",
    "sign.other": "Outro sinal",
    "light.street_lamp": "Candeeiro",
    "light.street_pole": "Poste de luz",
    "waste.underground": "Contentor subterrâneo",
    "waste.recycling_island": "Ecoponto (ilha de reciclagem)",
    "waste.general": "Contentor indiferenciado",
}

CLASS_NAMES: tuple[str, ...] = tuple(LABELS)


def split_class(name: str) -> tuple[ElementCategory, str]:
    """'sign.speed_limit' -> (ElementCategory.TRAFFIC_SIGN, 'speed_limit'). ValueError if unknown"""
    category, _, type_ = name.partition(".")
    if not type_:
        raise ValueError(f"'{name}' is not 'category.type'")
    return ElementCategory(category), type_


def class_name(category: ElementCategory, type_: str | None) -> str:
    return f"{category.value}.{type_ or 'other'}"


def label(name: str) -> str:
    """Human name for a class, e.g. 'Limite de velocidade'."""
    return LABELS.get(name) or name.partition(".")[2].replace("_", " ").capitalize() or name
