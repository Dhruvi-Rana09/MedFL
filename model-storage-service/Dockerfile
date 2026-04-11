FROM python:3.10

WORKDIR /app

COPY . .

<<<<<<< HEAD
RUN pip install --no-cache-dir -r requirements.txt
=======
RUN mkdir -p /app/data

COPY app/ .
>>>>>>> 1388b1ba2d3f5fa08b567c79fbd06e5cbc1bea10

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]