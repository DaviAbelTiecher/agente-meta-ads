FROM python:3.10-slim

WORKDIR /app

# Instala dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Expõe a porta 5000
EXPOSE 5000

# Comando para iniciar o servidor Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "server:app"]
