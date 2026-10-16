FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY quorum ./quorum
COPY frontend ./frontend
COPY recordings ./recordings
RUN useradd --create-home --uid 10001 desk && chown -R desk /app
USER desk
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn quorum.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
