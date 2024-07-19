# Use an appropriate base image
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . /app
WORKDIR /app

# Run your application
CMD ["uvicorn", "ysf:app", "--host", "0.0.0.0", "--port", "8000"]
