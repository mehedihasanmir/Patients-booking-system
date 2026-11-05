FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY main.py ./
COPY bytevoice_agent ./bytevoice_agent
RUN pip install --no-cache-dir .
RUN python main.py download-files || echo "model files will download on first start"

CMD ["python", "main.py", "start"]
