import pytest

from src.taxonomy import Taxonomy


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.model_validate(
        {
            "classes": [
                {"name": "sign.stop", "label": "Stop"},
                {"name": "sign.other", "label": "Outro"},
                {"name": "light.street_lamp", "label": "Candeeiro", "ground": True},
                {"name": "waste.general", "label": "Indiferenciado", "ground": True},
            ]
        }
    )
