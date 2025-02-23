# Use the official Python image
FROM python:3.11

# Install system dependencies (including libgl1 for OpenCV)
RUN apt-get update && apt-get install -y libgl1

# Set the working directory inside the container
WORKDIR /server

# Copy the application files to the working directory
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 8000

# Command to run Uvicorn when the container starts
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
