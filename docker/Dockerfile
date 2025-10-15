# Use slim python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# IMPORTANT: This Dockerfile expects the build context to be the repository root.
# If you run the docker build command from inside the `docker/` directory, pass
# `..` as the build context so paths like `backend/requirements.txt` are
# resolved relative to the repository root. Example (from docker/):
#   docker build -f Dockerfile -t <tag> ..

# Install system dependencies (needed for psycopg2 and others)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Default command (backend runs by default; overridden in docker-compose for streamlit)
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
