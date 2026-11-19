import pytest

from src.taxonomy import Taxonomy


@pytest.fixture
def taxonomy() -> Taxonomy:
    return Taxonomy.model_validate(
        {
            "classes": [
                {
                    "name": "sign.stop",
                    "label": "Stop",
                    "ground": False,
                    "size": {"dim": "width", "m": 0.6, "tol": 0.15},
                },
                {
                    "name": "light.street_lamp",
                    "label": "Candeeiro",
                    "ground": True,
                    "size": {"dim": "height", "m": 6.0, "tol": 0.4},
                },
                {
                    "name": "waste.underground",
                    "label": "Subterrâneo",
                    "ground": True,
                    "size": None,
                },
            ]
        }
    )
