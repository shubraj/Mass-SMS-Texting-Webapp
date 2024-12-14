FROM python:3.11-alpine

# Install system dependencies for MySQL
RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    mariadb-dev

# Set the working directory
WORKDIR /app

# Install Python dependencies from requirements.txt
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . /app/

# Expose port 8000 for the application
EXPOSE 8000

# Run Gunicorn as the application server
CMD ["gunicorn", "smstexting.wsgi:application", "--bind", "0.0.0.0:8000"]
