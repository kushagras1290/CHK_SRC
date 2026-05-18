FROM mcr.microsoft.com/playwright/python:v1.59.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -e .

RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/output /app/playwright/.auth && \
    chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["chakra-scraper"]
CMD ["--help"]
