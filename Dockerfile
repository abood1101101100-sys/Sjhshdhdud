FROM nikolaik/python-nodejs:python3.10-nodejs18

RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        ntpdate \
        tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=UTC

WORKDIR /app/
COPY . /app/
RUN mkdir -p /app/downloads

RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir --upgrade -r requirements.txt

CMD ntpdate -u pool.ntp.org; bash start
