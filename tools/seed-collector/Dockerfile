FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /data

# Environment variables
ENV QUEUE_FILE=/data/queued_seeds.jsonl
ENV HOST=0.0.0.0
ENV PORT=8091

EXPOSE 8091

# Run the application
CMD ["python", "main.py"]
