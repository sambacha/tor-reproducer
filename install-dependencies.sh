#!/usr/bin/env bash
set -e
set -x

apt-get install -y --no-install-recommends \
	git \
	zip \
	unzip \
	wget \
	build-essential \
	make \
	patch \
	pkg-config \
	autopoint \
	libtool \
	automake \
	binutils-multiarch \
	fastjar \
	gcc-aarch64-linux-gnu \
	libc6-dev-arm64-cross \
	gcc-arm-linux-gnueabihf \
	libc6-dev-armhf-cross \
	gcc-mingw-w64-x86-64 \
	libc6-dev-amd64-cross \
	perl \
	po4a
