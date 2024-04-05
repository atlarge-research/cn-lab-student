FROM ubuntu:latest

RUN apt-get update && apt-get install -y \
    netcat \
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

RUN rm /home/compnet/chat_client_check/client.py \
    /home/compnet/dns_check/dns.py \
    /home/compnet/server_check/server.py \
    /home/compnet/http_server_check/server.py \
    /home/compnet/unreliable_chat_check/client.py

RUN pip install -r requirements.txt
