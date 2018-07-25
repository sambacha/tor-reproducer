#!/usr/bin/env python3
import os
import sys
from subprocess import check_call, CalledProcessError

from utils import REPO_DIR, get_sha256, fail, get_build_versions, get_final_file_name, \
    get_version, get_tor_version


def main():
    # get Tor version from command or show usage information
    version = get_version()

    # get Tor version and versions of its dependencies
    versions = get_build_versions(version)

    # download reference binary
    file_name = get_final_file_name(versions)
    try:
        # try downloading from jcenter
        check_call(['wget', '--no-verbose', get_url(versions), '-O', file_name])
    except CalledProcessError:
        # try fallback to bintray
        print("Warning: Download from jcenter failed. Trying bintray directly...")
        check_call(['wget', '--no-verbose', get_url(versions, fallback=True), '-O', file_name])

    # check if Tor was already build
    build_file_name = os.path.join(REPO_DIR, file_name)
    if not os.path.isfile(build_file_name):
        # build Tor
        if version is None:
            check_call(['./build-tor.py'])
        else:
            check_call(['./build-tor.py', version])

    # calculate hashes for both files
    reference_hash = get_sha256(file_name)
    build_hash = get_sha256(build_file_name)
    print("Reference sha256: %s" % reference_hash)
    print("Build sha256:     %s" % build_hash)

    # compare hashes
    if reference_hash == build_hash:
        print("Tor version %s was successfully verified! \o/" % versions['tor'])
        sys.exit(0)
    else:
        fail("Hashes do not match :(")


def get_url(versions, fallback=False):
    version = get_tor_version(versions)
    file = get_final_file_name(versions)
    if not fallback:
        return "https://jcenter.bintray.com/org/briarproject/tor-android/%s/%s" % (version, file)
    else:
        return "https://dl.bintray.com/briarproject/org.briarproject/org/briarproject/tor-android" \
               "/%s/%s" % (version, file)


if __name__ == "__main__":
    main()
