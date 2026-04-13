# Use a consistent, slim Python version across all services
FROM python:3.11-slim 

WORKDIR /app

COPY requirements.txt .
# Use --no-cache-dir to keep image sizes small
RUN pip install --no-cache-dir -r requirements.txt

# Preserve the 'app' directory namespace
COPY app/ ./app/
COPY certs/ ./certs/

# Run via the app namespace
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
