#!/usr/bin/env bash
set -e
set -x

apt-get install -y --no-install-recommends \
	git \
	zip \
	unzip \
	wget \
	make \
	patch \
	autopoint \
	libtool \
	automake \
	binutils-multiarch
