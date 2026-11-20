import json
from src.service.main import app

with open("docs/contract/openapi.json", "w", encoding="utf-8") as f:
    json.dump(app.openapi(), f, indent=2, ensure_ascii=False)
