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
	autopoint \
	libtool \
	automake \
	binutils-multiarch \
	fastjar \
	gcc-aarch64-linux-gnu \
	libc6-dev-arm64-cross \
	gcc-arm-linux-gnueabihf \
	libc6-dev-armhf-cross \
	gcc-arm-linux-gnueabi \
	libc6-dev-armel-cross \
	perl
