FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and clean up scripts first
COPY requirements.txt create_railway_config.py full_custom_dl_removal.py clean_ytdlp_patch.py complete_custom_dl_removal.py ./

# Remove any banned dependencies
RUN grep -v "null_downloader" requirements.txt > clean_requirements.txt || true
RUN cat clean_requirements.txt > requirements.txt || true

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV HTTP_DOWNLOADER=native \
    YTDLP_DOWNLOADER=native \
    NO_EXTERNAL_DOWNLOADER=1 \
    DISABLE_EXTERNAL_DL=true \
    YDL_NO_EXTERNAL_DOWNLOADER=1 \
    YDL_VERBOSE_NO_EXTERNAL_DL=1

# Run cleanup scripts
RUN python create_railway_config.py || true
RUN python full_custom_dl_removal.py || true
RUN python clean_ytdlp_patch.py || true
RUN python complete_custom_dl_removal.py || true

# Copy all application files
COPY . .

# Create necessary directories
RUN mkdir -p /app/downloads && chmod 777 /app/downloads
RUN mkdir -p /tmp/ytdlp_temp && chmod 777 /tmp/ytdlp_temp

# Final cleanup 
RUN find / -name "*null_downloader*" -type f -delete 2>/dev/null || true

# Command to run
CMD ["python", "telegram_downloader.py"]
