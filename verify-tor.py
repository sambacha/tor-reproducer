#!/usr/bin/env python3
import os
import sys
from subprocess import check_call, CalledProcessError

from utils import get_sha256, get_build_versions, get_final_file_name, \
    get_version, get_version_tag

REF_DIR = "reference"


def main():
    # get Tor version from command or show usage information
    version = get_version()

    if verify(version, for_android=False) and verify(version, for_android=True):
        sys.exit(0)
    else:
        sys.exit(1)


def verify(version, for_android):
    # get Tor version and versions of its dependencies
    versions = get_build_versions(version)

    # download reference binary
    os.makedirs(REF_DIR, exist_ok=True)
    file_name = get_final_file_name(versions, for_android)
    ref_file = os.path.join(REF_DIR, file_name)
    try:
        # try downloading from jcenter
        check_call(['wget', '--no-verbose', get_url(versions, for_android), '-O', ref_file])
    except CalledProcessError:
        # try fallback to bintray
        print("Warning: Download from jcenter failed. Trying bintray directly...")
        check_call(['wget', '--no-verbose', get_url(versions, for_android, fallback=True), '-O',
                    ref_file])

    # check if Tor was already build
    if not os.path.isfile(file_name):
        # build Tor
        if version is None:
            check_call(['./build-tor.py'])
        else:
            check_call(['./build-tor.py', version])

    # calculate hashes for both files
    reference_hash = get_sha256(ref_file)
    build_hash = get_sha256(file_name)
    print("Reference sha256: %s" % reference_hash)
    print("Build sha256:     %s" % build_hash)

    # compare hashes
    suffix = " for Android" if for_android else ""
    if reference_hash == build_hash:
        print("Tor%s version %s was successfully verified! \\o/" % (suffix, versions['tor']))
        return True
    else:
        print("Hashes for Tor%s version %s do not match! :(" % (suffix, versions['tor']))
        return False


def get_url(versions, for_android, fallback=False):
    version = get_version_tag(versions)
    directory = "tor-android" if for_android else "tor"
    file = get_final_file_name(versions, for_android)
    if not fallback:
        return "https://jcenter.bintray.com/org/briarproject/%s/%s/%s" % (directory, version, file)
    else:
        return "https://dl.bintray.com/briarproject/org.briarproject/org/briarproject/%s/%s/%s" % \
               (directory, version, file)


if __name__ == "__main__":
    main()
