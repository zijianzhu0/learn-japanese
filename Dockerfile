FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        ffmpeg \
        fonts-noto-cjk \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install --global @openai/codex

WORKDIR /app

COPY . .

ENV HOST=0.0.0.0
ENV PORT=8765

EXPOSE 8765

CMD ["python", "-m", "server.local_tts_server"]
