FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install flask==3.1.3
WORKDIR /app
COPY app.py config.json /app/
EXPOSE 8080
CMD ["python", "app.py"]
