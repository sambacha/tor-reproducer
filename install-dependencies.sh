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
	perl \
	autopoint
