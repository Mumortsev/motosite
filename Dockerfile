FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=80

COPY server.py system_prompt.txt amvera.yml ./
COPY index.html gemini-code-1792671903411.html ./
COPY images/ ./images/

RUN mkdir -p /app/.cache

EXPOSE 80

CMD ["python", "-u", "server.py"]
