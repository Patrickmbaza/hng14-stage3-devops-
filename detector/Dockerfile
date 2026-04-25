FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends iptables \
    && rm -rf /var/lib/apt/lists/*

COPY detector/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY detector /app/detector

EXPOSE 8081

CMD ["python", "-m", "detector.main"]
