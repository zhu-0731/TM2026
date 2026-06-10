# Copyright 2024 Google LLC
# Licensed under the Apache License, Version 2.0

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /coupon_server

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
ENTRYPOINT ["python", "main.py"]
