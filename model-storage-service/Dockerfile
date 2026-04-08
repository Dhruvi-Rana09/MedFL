FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN mkdir -p /app/data

COPY app/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]