# Base image for gateway, indexer and egress proxy.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"
COPY ufinder ./ufinder
COPY ui ./ui
RUN useradd -u 10001 -M ufinder && mkdir -p /data /exchange && chown 10001 /data /exchange
USER 10001
