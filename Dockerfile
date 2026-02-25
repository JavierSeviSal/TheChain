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

# Create saves directory writable by any user (HF Spaces may run as non-root)
RUN mkdir -p saves && chmod 777 saves

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app:app"]
