FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY app.py .
COPY game/ game/
COPY static/ static/
COPY templates/ templates/

# Create saves directory (will be overridden by volume mount)
RUN mkdir -p saves

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", "app:app"]
