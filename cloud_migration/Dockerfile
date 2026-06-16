FROM python:3.11-slim

WORKDIR /app

# Install Python deps
COPY requirements_cloud.txt .
RUN pip install --no-cache-dir -r requirements_cloud.txt

# Copy bridge + modules
COPY gerald_bridge.py .
COPY build_verifier.py .
COPY multi_ai_router.py .

# Data dir for status/outbox JSON files
RUN mkdir -p /app/data
ENV GERALD_DATA_DIR=/app/data

EXPOSE 8000

CMD ["uvicorn", "gerald_bridge:app", "--host", "0.0.0.0", "--port", "8000"]
