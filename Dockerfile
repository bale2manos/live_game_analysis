# ---- Imagen base ----
FROM python:3.11-slim

# ---- Dependencias del sistema ----
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    chromium \
    chromium-driver \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
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

# ---- Directorio de trabajo ----
WORKDIR /app
COPY . /app

# ---- Instalar dependencias Python ----
RUN pip install --no-cache-dir -r requirements.txt

# ---- Variables de entorno necesarias ----
ENV PYTHONUNBUFFERED=1
ENV PORT=8501

# Render busca siempre que la app escuche en 0.0.0.0
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]