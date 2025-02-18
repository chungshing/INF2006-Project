# Use official Python image
FROM python:3.9

# Set working directory
WORKDIR /app

# Copy application files to container
COPY . /app

# Install virtual environment
RUN python -m venv venv

# Activate virtual environment and install dependencies
RUN . venv/bin/activate && pip install --no-cache-dir -r requirements.txt

# Expose port 5000 for Flask
EXPOSE 5000

# Run Flask inside virtual environment
CMD ["sh", "-c", ". venv/bin/activate && python app.py"]
