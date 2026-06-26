FROM nikolaik/python-nodejs:python3.10-nodejs18

# Install system dependencies
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/

# Copy project files
COPY . /app/

# Create downloads directory
RUN mkdir -p /app/downloads

# Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir --upgrade -r requirements.txt

# Run the bot
CMD bash start
