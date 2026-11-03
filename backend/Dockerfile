# Build from the repository root so the in-process `rag` package is available:
#   docker build -f backend/Dockerfile .
FROM python:3.11-slim

WORKDIR /srv

COPY requirements.txt ./requirements-rag.txt
COPY backend/requirements.txt ./requirements-backend.txt
RUN pip install --no-cache-dir -r requirements-rag.txt -r requirements-backend.txt

COPY rag ./rag
COPY backend ./backend
COPY scripts ./scripts

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
