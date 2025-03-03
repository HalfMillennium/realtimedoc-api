# Build Stage
FROM python:3.11-slim AS builder
WORKDIR /server

# Install system dependencies for building
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 \
    gcc \
    python3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies into a dedicated install path
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final Stage (lighter runtime container)
FROM python:3.11-slim
WORKDIR /server

# Install only runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy only necessary files from builder stage
COPY --from=builder /install /usr/local
COPY . .

# Expose the application port
EXPOSE 8000

# Command to run Uvicorn when the container starts
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]