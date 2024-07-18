# Utiliser une image de base avec Python 3.9
FROM python:3.9-slim

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean

# Copier le fichier requirements.txt et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code de l'application
COPY . /app

# Définir le répertoire de travail
WORKDIR /app

# Exposer le port sur lequel FastAPI s'exécutera
EXPOSE 8000

# Commande pour démarrer le serveur FastAPI avec Uvicorn
CMD ["uvicorn", "ysf:app", "--host", "0.0.0.0", "--port", "8000"]
