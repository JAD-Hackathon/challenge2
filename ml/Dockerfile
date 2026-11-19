FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/ml/.venv/bin:$PATH" \
    TORCH_HOME=/ml/weights/torch \
    HF_HOME=/ml/weights/hf

WORKDIR /ml
ARG TORCH_VARIANT=cpu

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project \
        --no-install-package torch --no-install-package torchvision \
 && uv pip install --python /ml/.venv/bin/python --no-cache \
        torch torchvision --index-url https://download.pytorch.org/whl/${TORCH_VARIANT}

COPY src/ ./src/
COPY configs/ ./configs/

RUN mkdir -p /ml/weights /data/images

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "src.service.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
