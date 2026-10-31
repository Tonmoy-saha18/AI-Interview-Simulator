FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

EXPOSE 8001

CMD ["uvicorn", "judge_service.api:app", "--host", "0.0.0.0", "--port", "8001"]
