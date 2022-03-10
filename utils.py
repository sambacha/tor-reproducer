#!/usr/bin/env python3

import hashlib
import json
import os
import sys
from collections import OrderedDict
from shutil import copy, rmtree
from subprocess import check_call

BUILD_DIR = 'tor-build'
TOR_CONFIGURE_FLAGS = [
    '--disable-asciidoc',
    '--disable-systemd',
    '--disable-tool-name-check',
    '--disable-module-relay',
    '--disable-module-dirauth',
    '--disable-unittests',
    '--disable-asciidoc',
    '--disable-manpage',
    '--disable-html-manual',
]
XZ_CONFIGURE_FLAGS = [
    '--enable-static',
    '--disable-doc',
    '--disable-lzma-links',
    '--disable-lzmadec',
    '--disable-lzmainfo',
    '--disable-scripts',
    '--disable-shared',
    '--disable-xz',
    '--disable-xzdec',
]
OPENSSL_CONFIGURE_FLAGS = [
    'no-unit-test',
    'no-asm',
    'no-comp',
    'no-dtls',
    'no-err',
    'no-psk',
    'no-srp',
    'no-weak-ssl-ciphers',
    'no-camellia',
    'no-idea',
    'no-md2',
    'no-md4',
    'no-rc2',
    'no-rc4',
    'no-rc5',
    'no-rmd160',
    'no-whirlpool',
    'no-ui-console',
]
REPRODUCIBLE_GCC_CFLAGS = '-fno-guess-branch-probability -frandom-seed="0"'

def get_output_dir(platform):
    return os.path.abspath(os.path.join(BUILD_DIR, 'output', platform))

def setup(platform):
    # get Tor version from command or show usage information
    version = get_version()

    # get Tor version and versions of its dependencies
    versions = get_build_versions(version)
    print("Building Tor %s" % versions['tor']['commit'])

    # remove output from previous build
    output_dir = get_output_dir(platform)
    if os.path.isdir(output_dir):
        rmtree(output_dir)
    os.makedirs(output_dir)

    # clone and checkout repos based on tor-versions.json
    prepare_repos(versions)

    # create sources jar before building
    jar_name = create_sources_jar(versions, platform)

    return versions, jar_name


def prepare_repos(versions):
    prepare_repo(os.path.join(BUILD_DIR, "tor"), versions['tor']['url'], versions['tor']['commit'])
    prepare_repo(os.path.join(BUILD_DIR, "libevent"), versions['libevent']['url'], versions['libevent']['commit'])
    prepare_repo(os.path.join(BUILD_DIR, "openssl"), versions['openssl']['url'], versions['openssl']['commit'])
    prepare_repo(os.path.join(BUILD_DIR, "xz"), versions['xz']['url'], versions['xz']['commit'])
    prepare_repo(os.path.join(BUILD_DIR, "zlib"), versions['zlib']['url'], versions['zlib']['commit'])
    prepare_repo(os.path.join(BUILD_DIR, "zstd"), versions['zstd']['url'], versions['zstd']['commit'])


def prepare_repo(path, url, version):
    if os.path.isdir(path):
        # get latest commits and tags from remote
        check_call(['git', 'fetch', '--recurse-submodules=yes', 'origin'], cwd=path)
    else:
        # clone repo
        check_call(['git', 'clone', url, path])

    # checkout given version
    check_call(['git', 'checkout', '-f', version], cwd=path)

    # initialize and/or update submodules
    # (after checkout, because submodules can point to non-existent commits on master)
    check_call(['git', 'submodule', 'update', '--init', '--recursive', '-f'], cwd=path)

    # undo all changes
    check_call(['git', 'reset', '--hard'], cwd=path)
    check_call(['git', 'submodule', 'foreach', 'git', 'reset', '--hard'], cwd=path)

    # clean all untracked files and directories (-d) from repo
    check_call(['git', 'clean', '-dffx'], cwd=path)
    check_call(['git', 'submodule', 'foreach', 'git', 'clean', '-dffx'], cwd=path)


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
    return 'tor-%s.jar' % get_file_suffix(versions, platform)


def get_sources_file_name(versions, platform):
    return 'tor-%s-sources.jar' % get_file_suffix(versions, platform)


def get_pom_file_name(versions, platform):
    return 'tor-%s.pom' % get_file_suffix(versions, platform)


def pack(versions, file_list, platform):
    # make file times deterministic before zipping
    for filename in file_list:
        reset_time(filename, versions)
    zip_name = get_final_file_name(versions, platform)
    check_call(['zip', '--no-dir-entries', '--junk-paths', '-X', zip_name] + file_list)
    return zip_name


def reset_time(filename, versions):
    check_call(['touch', '--no-dereference', '-t', versions['timestamp'], filename])


def create_sources_jar(versions, platform):
    output_dir = get_output_dir(platform)
    jar_files = []
    for root, dir_names, filenames in os.walk(BUILD_DIR):
        for f in filenames:
            if '/.git' in root:
                continue
            jar_files.append(os.path.join(root, f))
    for file in jar_files:
        reset_time(file, versions)
    jar_name = get_sources_file_name(versions, platform)
    jar_path = os.path.abspath(jar_name)
    rel_paths = [os.path.relpath(f, output_dir) for f in sorted(jar_files)]
    # create jar archive with first files
    jar_step = 5000
    check_call(['jar', 'cf', jar_path] + rel_paths[0:jar_step], cwd=output_dir)
    # add subsequent files in steps, because the command line can't handle all at once
    for i in range(jar_step, len(rel_paths), jar_step):
        check_call(['jar', 'uf', jar_path] + rel_paths[i:i + jar_step], cwd=output_dir)
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
