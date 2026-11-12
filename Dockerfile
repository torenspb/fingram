# Official multi-architecture image: builds natively for amd64 and arm64.
FROM python:3.15.2-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/fingram
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 fingram \
    && useradd --uid 10001 --gid fingram --no-create-home fingram
COPY bot.py main.py ./
USER 10001:10001
CMD ["python", "bot.py"]
