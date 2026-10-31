FROM python:3.13-alpine AS builder

WORKDIR /usr/src/app

COPY app/requirements.txt .

RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt

FROM python:3.13-alpine

WORKDIR /usr/src/app

# Instalar dependencias del sistema
RUN apk add --no-cache tzdata && \
    ln -snf /usr/share/zoneinfo/America/Mexico_City /etc/localtime && \
    echo "America/Mexico_City" > /etc/timezone

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV TZ=America/Mexico_City
ENV PYTHONPATH=/usr/src/app

# Copiar dependencias
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache /wheels/* && \
    rm -rf /wheels

# Copiar aplicación
COPY app/ .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
