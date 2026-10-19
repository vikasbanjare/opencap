# Hugging Face Space (Docker SDK): builds the web app, then serves it and the API from one uvicorn on 7860.
FROM oven/bun:1 AS web
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY . .
RUN bun run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
USER user
# ponytail: "small" Whisper keeps transcription usable on the free 2-vCPU tier; set OPENCAP_WHISPER in Space settings for large-v3-turbo
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH OPENCAP_WHISPER=small
WORKDIR /home/user/app
COPY --chown=user server/requirements.txt server/
RUN pip install --no-cache-dir --user -r server/requirements.txt kokoro-onnx soundfile sentencepiece
RUN python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['OPENCAP_WHISPER'], device='cpu', compute_type='int8')"
RUN mkdir -p server/models && cd server/models && \
    curl -fsSLO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx && \
    curl -fsSLO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
COPY --chown=user server/*.py server/
COPY --from=web --chown=user /app/dist dist
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--app-dir", "server"]
