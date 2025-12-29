FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

# Cloud Run uses PORT env variable
ENV PORT=8080
EXPOSE 8080

# Run the application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]