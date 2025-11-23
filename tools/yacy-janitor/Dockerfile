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
ENV YACY_URL=http://yacy:8090
ENV DATA_DIR=/data

# Run the application
CMD ["python", "main.py"]
