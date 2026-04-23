FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 5 -r requirements.txt
COPY . .

# Generate RSA key pair for JWT signing if not already present
RUN mkdir -p certs && \
    openssl genrsa -out certs/private.pem 2048 && \
    openssl rsa -in certs/private.pem -pubout -out certs/public.pem

EXPOSE 8000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
