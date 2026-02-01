FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
COPY scrapers/ /scrapers/
COPY utils/ /utils/
COPY config/ /config/

ENV PYTHONPATH="/:/scrapers:/utils:/config:${PYTHONPATH}"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
