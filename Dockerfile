# Use slim Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install OS dependencies
RUN apt-get update && apt-get install -y \
    curl gcc libpq-dev build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Create and activate virtual environment
RUN python -m venv .venv \
    && .venv/bin/pip install --upgrade pip \
    && .venv/bin/pip install -r requirements.lock

# Set PATH to use venv
ENV PATH="/app/.venv/bin:$PATH"

# Run main.py using venv's Python
CMD ["python", "main.py"]
