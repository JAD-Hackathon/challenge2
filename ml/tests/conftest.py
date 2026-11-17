import pytest
from src.config import DetectionConfig
from src.taxonomy import Taxonomy

CLASS_MAP = {"traffic_sign": "sign.other", "street_lamp": "light.street_lamp"}


@pytest.fixture
def tax() -> Taxonomy:
    return Taxonomy.model_validate(
        {
            "classes": [
                {"name": "sign.other", "label": "Outro sinal"},
                {"name": "light.street_lamp", "label": "Candeeiro"},
            ]
        }
    )


@pytest.fixture
def cfg() -> DetectionConfig:
    # needs `class_map` and `model_id` fields in DetectionConfig
    return DetectionConfig(conf=0.3, class_map=CLASS_MAP, model_id="test/model")
