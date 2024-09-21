# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file into the container at /app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Define environment variables
ENV WEBHOOK_VERIFY_TOKEN=WhatsApp_Token_J
ENV MONGODB_URI=mongodb+srv://maabanejubilant6:tbtQCFdA3dB4NHQI@backenddb.dorynel.mongodb.net
ENV GRAPH_API_TOKEN=EAAMFIfw2OXABOZCa77eHVHv8vdDoeCov8wi9ZCH3KnJNTZBiIaMZC3PViu8ueLvkODnqipMFyvDnW5imfL4AEUhQnfBse5X9dYCDcBoTLXKB0GHpaVZCh9DeYUooigeCRLTFj3qOZA9Y3DmFEPvf7gl120IRqJqAq42SzZBSIaQcfhKq7B8nZBLEAZBRC7w714Dh9

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run FastAPI app with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
