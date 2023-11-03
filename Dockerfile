FROM python:alpine
WORKDIR /app
COPY requirements.txt ./
COPY server.py ./
RUN pip install --no-cache-dir -r /app/requirements.txt
EXPOSE 8000
CMD ["python", "server.py"]
