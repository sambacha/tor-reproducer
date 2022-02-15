#!/usr/bin/env python3

import hashlib
import json
import os
import sys
from collections import OrderedDict
from shutil import copy
from subprocess import check_call

REPO_DIR = 'tor-android'
ZLIB_REPO_URL = 'https://github.com/madler/zlib.git'
EXT_DIR = os.path.abspath(os.path.join(REPO_DIR, 'external'))


def setup(platform):
    # get Tor version from command or show usage information
    version = get_version()

    # get Tor version and versions of its dependencies
    versions = get_build_versions(version)
    print("Building Tor %s" % versions['tor'])

    # clone and checkout tor-android repo based on tor-versions.json
    prepare_tor_android_repo(versions)

    # create sources jar before building
    jar_name = create_sources_jar(versions, platform)

    return versions, jar_name


def package_geoip(versions):
    # zip geoip database
    geoip_path = os.path.join(REPO_DIR, 'geoip')
    copy(os.path.join(EXT_DIR, 'tor', 'src', 'config', 'geoip'), geoip_path)
    reset_time(geoip_path, versions)
    check_call(['zip', '-X', '../geoip.zip', 'geoip'], cwd=REPO_DIR)


def prepare_tor_android_repo(versions):
    if os.path.isdir(REPO_DIR):
        # get latest commits and tags from remote
        check_call(['git', 'fetch', '--recurse-submodules=yes', 'origin'], cwd=REPO_DIR)
    else:
        # clone repo
        url = versions['tor_android_repo_url']
        check_call(['git', 'clone', url, REPO_DIR])

    # checkout tor-android version
    check_call(['git', 'checkout', '-f', versions['tor-android']], cwd=REPO_DIR)

    # initialize and/or update submodules
    # (after checkout, because submodules can point to non-existent commits on master)
    check_call(['git', 'submodule', 'update', '--init', '--recursive', '-f'], cwd=REPO_DIR)

    # undo all changes
    check_call(['git', 'reset', '--hard'], cwd=REPO_DIR)
    check_call(['git', 'submodule', 'foreach', 'git', 'reset', '--hard'], cwd=REPO_DIR)

    # clean all untracked files and directories (-d) from repo
    check_call(['git', 'clean', '-dffx'], cwd=REPO_DIR)
    check_call(['git', 'submodule', 'foreach', 'git', 'clean', '-dffx'], cwd=REPO_DIR)

    # add zlib
    check_call(['git', 'clone', ZLIB_REPO_URL], cwd=EXT_DIR)

    # check out versions of external dependencies
    checkout('tor', versions['tor'], 'tor')
    checkout('libevent', versions['libevent'], 'libevent')
    checkout('openssl', versions['openssl'], 'openssl')
    checkout('xz', versions['xz'], 'xz')
    checkout('zlib', versions['zlib'], 'zlib')
    checkout('zstd', versions['zstd'], 'zstd')


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


def get_file_suffix(versions, platform):
    version = get_version_tag(versions)
    return "%s-%s" % (platform, version)


def get_final_file_name(versions, platform):
    version = get_version_tag(versions)
    if version < '0.3.5.14':
        return 'tor-%s.zip' % get_file_suffix(versions, platform)
    else:
        return 'tor-%s.jar' % get_file_suffix(versions, platform)


def get_sources_file_name(versions, platform):
    return 'tor-%s-sources.jar' % get_file_suffix(versions, platform)


def get_pom_file_name(versions, platform):
    return 'tor-%s.pom' % get_file_suffix(versions, platform)


def checkout(name, tag, path):
    print("Checking out %s: %s" % (name, tag))
    repo_path = os.path.join(EXT_DIR, path)
    check_call(['git', 'checkout', '-f', tag], cwd=repo_path)


def pack(versions, file_list, platform):
    # make file times deterministic before zipping
    for filename in file_list:
        reset_time(filename, versions)
    zip_name = get_final_file_name(versions, platform)
    check_call(['zip', '-D', '-X', zip_name] + file_list)
    return zip_name


def reset_time(filename, versions):
    if 'timestamp' in versions:
        timestamp = versions['timestamp']
    else:
        timestamp = '197001010000.00'
    check_call(['touch', '--no-dereference', '-t', timestamp, filename])


def create_sources_jar(versions, platform):
    jar_files = []
    for root, dir_names, filenames in os.walk(EXT_DIR):
        for f in filenames:
            if '/.git' in root:
                continue
            jar_files.append(os.path.join(root, f))
    for file in jar_files:
        reset_time(file, versions)
    jar_name = get_sources_file_name(versions, platform)
    jar_path = os.path.abspath(jar_name)
    rel_paths = [os.path.relpath(f, EXT_DIR) for f in sorted(jar_files)]
    check_call(['jar', 'cf', jar_path] + rel_paths, cwd=EXT_DIR)
    return jar_name


def create_pom_file(versions, platform):
    version = get_version_tag(versions)
    pom_name = get_pom_file_name(versions, platform)
    template = 'template-%s.pom' % platform
    with open(template, 'rt') as infile:
        with open(pom_name, 'wt') as outfile:
            for line in infile:
                outfile.write(line.replace('VERSION', version))
    return pom_name
