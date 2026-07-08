FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source code
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Expose backend port (Render / Railway inject $PORT; defaults to 8000 locally)
EXPOSE 8000

# Start both ML inference (background, port 8001) + FastAPI (foreground, $PORT)
CMD ["./start.sh"]
