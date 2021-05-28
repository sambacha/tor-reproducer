#!/usr/bin/env python3

import hashlib
import json
import sys
from collections import OrderedDict

REPO_DIR = 'tor-android'


def get_version():
    if len(sys.argv) > 2:
        fail("Usage: %s [Tor version tag]" % sys.argv[0])
    return sys.argv[1] if len(sys.argv) > 1 else None


def get_build_versions(tag):
    # load Tor versions and their dependencies
    with open('tor-versions.json', 'r') as f:
        versions = json.load(f, object_pairs_hook=OrderedDict)

    if tag is None:
        # take top-most Tor version
        tag = next(iter(versions))
    versions[tag]['tag'] = tag
    return versions[tag]


def fail(msg=""):
    sys.stderr.write("Error: %s\n" % msg)
    sys.exit(1)


def get_sha256(filename, block_size=65536):
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            sha256.update(block)
    return sha256.hexdigest()


def get_version_tag(versions):
    return versions['tag']


def get_file_suffix(versions, android=False):
    version = get_version_tag(versions)
    return "%s-%s" % ("android", version) if android else version


def get_final_file_name(versions, android=False):
    version = get_version_tag(versions)
    if version < '0.3.5.14':
        return 'tor-%s.zip' % get_file_suffix(versions, android)
    else:
        return 'tor-%s.jar' % get_file_suffix(versions, android)


def get_sources_file_name(versions, android=False):
    return 'tor-%s-sources.jar' % get_file_suffix(versions, android)


def get_pom_file_name(versions, android=False):
    return 'tor-%s.pom' % get_file_suffix(versions, android)
