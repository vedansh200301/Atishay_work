FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome options for Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_PATH=/usr/lib/chromium/
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Additional Chrome flags for running in container
ENV CHROME_FLAGS="--no-sandbox --headless --disable-gpu --disable-dev-shm-usage"

# Set application port
ENV PORT=8000

# Set up working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py pan_gstin_mapper_enhanced.py ultimate.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Create necessary directories and set permissions
RUN mkdir -p uploads results screenshots results/temp \
    && chmod -R 777 results uploads screenshots results/temp \
    && chmod -R 777 /usr/lib/chromium/ \
    && chmod 777 /usr/bin/chromedriver

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "app.py"]