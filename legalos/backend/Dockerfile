FROM python:3.11-slim

WORKDIR /app

# Basic Linux dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch (the default PyPI wheel drags in ~5 GB of CUDA libraries we never use).
# Installed first so the dependency install below sees torch as already satisfied.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies from pyproject.toml only (keeps this layer cached until deps change).
# poetry-core is the build backend, so `pip install .` resolves [tool.poetry.dependencies].
COPY pyproject.toml /app/
RUN mkdir -p /app/app && touch /app/app/__init__.py /app/README.md \
    && pip install --no-cache-dir . \
    && pip uninstall -y legalos-backend \
    && pip install --no-cache-dir pytest "pytest-asyncio>=0.23.5,<0.24" "reportlab>=4.2,<5" "pillow>=10.3,<11"

# Copy application source
COPY . /app

EXPOSE 8000

# Apply migrations, then run the server (hot reload for local development)
# A failed migration is logged loudly but does not crash-loop the container; /health reports it.
CMD ["sh", "-c", "alembic upgrade head || echo '!!! MIGRATION FAILED - see error above !!!'; uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
