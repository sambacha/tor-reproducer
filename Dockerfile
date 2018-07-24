FROM debian:stretch

ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /opt/tor-reproducer

ADD build-tor.py ./
ADD install*.sh ./
ADD tor-versions.json ./
ADD utils.py ./
ADD template.pom ./

RUN ./install.sh

CMD ./build-tor.py
