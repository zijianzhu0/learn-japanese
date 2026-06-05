FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

ENV HOST=0.0.0.0
ENV PORT=8765

EXPOSE 8765

CMD ["python", "server/local_tts_server.py"]
