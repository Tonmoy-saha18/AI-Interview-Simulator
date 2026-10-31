# AI Interview Simulator Backend - Docker image
FROM python:3.12-slim

# Prevent Python from writing pyc and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps only if needed (e.g. for pdf/docx libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first for better layer caching
COPY pyproject.toml ./

# Install dependencies (no dev) so we can run from mounted source in dev if needed
COPY src ./src
RUN pip install --no-cache-dir -e .

# Copy rest of application (alembic, scripts)
COPY alembic ./alembic
COPY alembic.ini ./

# Create directory for CV uploads
RUN mkdir -p uploads/cvs

# Entrypoint runs migrations then starts the server
COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "ai_interview_bot.api:app", "--host", "0.0.0.0", "--port", "8000"]
