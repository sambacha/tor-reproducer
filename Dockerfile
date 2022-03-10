FROM debian:bullseye

ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /opt/tor-reproducer

ADD install*.sh ./
RUN ./install.sh

ADD build_tor.py ./
ADD build_tor_android.py ./
ADD build_tor_linux.py ./
ADD build_tor_windows.py ./
ADD verify_tor.py ./
ADD verify_tor_utils.py ./
ADD verify_tor_android.py ./
ADD verify_tor_linux.py ./
ADD verify_tor_windows.py ./
ADD tor-versions.json ./
ADD utils.py ./
ADD template-android.pom ./
ADD template-linux.pom ./
ADD template-windows.pom ./
ADD tor-build/Makefile ./tor-build/

CMD ./build-tor.py
