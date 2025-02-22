FROM python:3.13-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# copy the application
COPY . .

ARG PORT
ENV PORT=${PORT:-8000}

EXPOSE ${PORT}

# Command to run the application
CMD fastapi run app.py --host 0.0.0.0 --port $PORT