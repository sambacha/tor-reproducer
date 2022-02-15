#!/usr/bin/env python3

import build_tor_android
import build_tor_linux
import build_tor_windows

build_tor_android.build()
build_tor_linux.build()
build_tor_windows.build()
