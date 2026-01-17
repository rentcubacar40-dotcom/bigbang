FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero (para cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación
COPY main.py .

# Variables de entorno
ENV PORT=8000
EXPOSE 8000

# Salud del contenedor
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import socket; socket.create_connection(('localhost', 8000), timeout=2)" || exit 1

# Comando de inicio
CMD ["python", "main.py"]
