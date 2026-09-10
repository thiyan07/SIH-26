# GramBiz AI - API Dockerfile (no download beyond base image at build time)
FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal (no extra download in loop)
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . --no-deps 2>&1 | head -n 20 || pip install fastapi uvicorn sqlalchemy psycopg[binary] pydantic pydantic-settings httpx python-dotenv slowapi python-multipart

COPY app ./app
COPY scripts ./scripts

ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
