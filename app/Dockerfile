# Stage 1 - Build wheels
FROM python:3.13-alpine AS builder

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt

# Stage 2 - Runtime
FROM python:3.13-alpine

WORKDIR /usr/src/app

# Set timezone and env variables
ENV TZ=America/Mexico_City
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy wheels from builder
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .

# Install dependencies
RUN pip install --no-cache /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# Dev
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]