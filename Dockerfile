FROM python:3.11-slim

WORKDIR /app

# Install standard dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy all platform source files
COPY . /app

# Ensure proper execution permissions
RUN chmod +x desk.py server.py

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080

# Start QuantDesk dual-market server
CMD ["python", "server.py"]
