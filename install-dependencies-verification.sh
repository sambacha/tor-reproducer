#!/usr/bin/env bash
set -e
set -x

apt-get install -y --no-install-recommends \
	python3-pip python3-setuptools python3-wheel \
	python3-libarchive-c \
	libmagic1

# Install latest diffoscope (version in Debian stable is outdated)
pip3 install diffoscope