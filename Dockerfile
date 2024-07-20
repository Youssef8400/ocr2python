# Utilisez une image de base officielle de Python
FROM python:3.9-slim

# Installer Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev

# Définissez le répertoire de travail
WORKDIR /app

# Copiez le fichier requirements.txt dans le conteneur
COPY requirements.txt .

# Installez les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiez le reste des fichiers de l'application dans le conteneur
COPY . .

# Exposez le port sur lequel FastAPI fonctionnera
EXPOSE 8000

# Définissez la commande pour démarrer l'application FastAPI
CMD ["uvicorn", "ysf:app", "--host", "0.0.0.0", "--port", "8000"]
