# Use the Python version chosen for the service
FROM python:3.12-slim

# Set the working directory inside the image
WORKDIR /app

# Copy requirements.txt into the working directory
COPY requirements.txt .

# Install its dependencies using pip without caching downloads
RUN python -m pip install --no-cache-dir -r requirements.txt

# Create the runtime user
RUN useradd --create-home --uid 10001 supplier

# Replace your existing application COPY with one that sets ownership.
COPY --chown=supplier:supplier app ./app

# Switch subsequent instructions to the runtime user
USER supplier

# Document the container's listening port
EXPOSE 8080

# Probe the running API
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"

# Server command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
