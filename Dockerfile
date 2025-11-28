# Imagen base estable
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para Chromium + Chromedriver
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    curl \
    chromium \
    chromium-driver \
    libglib2.0-0 \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libxtst6 \
    libxrandr2 \
    libxdamage1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de la app
WORKDIR /app
COPY . /app

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Variables necesarias para Streamlit en Render
ENV PYTHONUNBUFFERED=1
ENV PORT=8501

# Comando para lanzar Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
