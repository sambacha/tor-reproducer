#!/usr/bin/env python3
import os
import sys
from subprocess import check_call

from utils import get_sha256, get_build_versions, get_final_file_name, get_version_tag, get_version

REF_DIR = "reference"


def main(platform):
    # get Tor version from command or show usage information
    version = get_version()

    if verify(version, platform):
        sys.exit(0)
    else:
        sys.exit(1)


def verify(version, platform):
    # get Tor version and versions of its dependencies
    versions = get_build_versions(version)

    # download reference binary
    os.makedirs(REF_DIR, exist_ok=True)
    file_name = get_final_file_name(versions, platform)
    ref_file = os.path.join(REF_DIR, file_name)
    # try downloading from maven central
    check_call(['wget', '--no-verbose', get_url(versions, platform), '-O', ref_file])

    # check if Tor was already build
    if not os.path.isfile(file_name):
        # build Tor
        if version is None:
            check_call(["./build_tor_%s.py" % platform])
        else:
            check_call(["./build_tor_%s.py" % platform, version])

    # calculate hashes for both files
    reference_hash = get_sha256(ref_file)
    build_hash = get_sha256(file_name)
    print("Reference sha256: %s" % reference_hash)
    print("Build sha256:     %s" % build_hash)

    # compare hashes
    suffix = ""
    if platform == "android":
        suffix = " for Android"
    elif platform == "linux":
        suffix = " for Linux"
    elif platform == "windows":
        suffix = " for Windows"
    if reference_hash == build_hash:
        print("Tor%s version %s was successfully verified! \\o/" % (suffix, versions['tor']))
        return True
    else:
        print("Hashes for Tor%s version %s do not match! :(" % (suffix, versions['tor']))
        return False


def get_url(versions, platform):
    version = get_version_tag(versions)
    directory = "tor-%s" % platform
    file = get_final_file_name(versions, platform)
    return "https://repo.maven.apache.org/maven2/org/briarproject/%s/%s/%s" % (directory, version, file)
