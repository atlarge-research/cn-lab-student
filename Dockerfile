FROM ubuntu:latest

RUN apt-get update && apt-get install -y \
    software-properties-common \
    python3.10 \
    python3-pip \
    strace \
    openjdk-17-jdk \
    golang-go \
    dnsutils

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN useradd -ms /bin/bash compnet
USER root
WORKDIR /home/compnet

COPY . /home/compnet/

RUN pip install -r requirements.txt
