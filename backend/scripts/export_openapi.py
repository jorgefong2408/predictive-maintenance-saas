"""Exporta el esquema OpenAPI del backend a JSON -- es la fuente para el
codegen de tipos de TypeScript del frontend (ver frontend/package.json,
`npm run codegen`, y frontend/src/lib/api-schema.ts).

No necesita una base de datos real ni MLflow corriendo: FastAPI arma el
esquema a partir de las rutas y los modelos Pydantic, sin ejecutar ninguna
query ni conexión (SQLAlchemy crea el engine de forma perezosa).

Uso:
    uv run python backend/scripts/export_openapi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

# frontend/openapi.json: no es el contrato final (eso es api-schema.ts,
# generado y sí versionado) sino un artefacto intermedio -- gitignored.
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    OUTPUT_PATH.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"Esquema OpenAPI escrito en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
