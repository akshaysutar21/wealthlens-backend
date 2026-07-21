# Use Python 3.9 as the base image
FROM python:3.9

# Hugging Face Spaces run with user ID 1000. 
# We create a specific user to avoid permission issues when installing packages or caching.
RUN useradd -m -u 1000 user
USER user

# Set PATH for the new user
ENV PATH="/home/user/.local/bin:$PATH"

# Set the working directory
WORKDIR /home/user/app

# Copy the requirements file and install dependencies
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application code
COPY --chown=user . .

# Hugging Face exposes port 7860 by default
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
