# Use the official Python image
FROM python:3.11

# Set the working directory inside the container
WORKDIR /server

# Copy the application files to the working directory
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 8000

# Command to run Uvicorn when the container starts
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
