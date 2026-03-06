FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    libffi-dev \
    libssl-dev \
    build-essential \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy your actual app code
COPY . .

EXPOSE 8000

# Use Daphne (ASGI) instead of Gunicorn (WSGI) to support WebSocket connections
CMD python manage.py collectstatic --noinput && daphne -b 0.0.0.0 -p 8000 app.asgi:application
