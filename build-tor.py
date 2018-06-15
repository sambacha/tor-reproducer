#!/usr/bin/env python3
import os
import sys
from shutil import move, copy, rmtree
from subprocess import check_call

from utils import REPO_DIR, get_sha256, fail, get_build_versions, get_final_file_name, get_version

NDK_DIR = 'android-ndk'


def main():
    # get Tor version from command or show usage information
    version = get_version()

    # get Tor version and versions of its dependencies
    versions = get_build_versions(version)
    print("Building Tor %s" % versions['tor'])

    # setup Android NDK
    setup_android_ndk(versions)

    # clone and checkout tor-android repo based on tor-versions.json
    prepare_tor_android_repo(versions)

    # build Tor for various architectures
    build_architectures()

    # zip geoip database
    geoip_path = os.path.join(REPO_DIR, 'external', 'tor', 'src', 'config', 'geoip')
    reset_time(geoip_path)
    check_call(['zip', '-D', '-X', os.path.join(REPO_DIR, 'geoip.zip'), geoip_path])

    # zip everything together
    file_list = ['tor_arm_pie.zip', 'tor_arm.zip', 'tor_x86_pie.zip', 'tor_x86.zip', 'geoip.zip']
    for filename in file_list:
        reset_time(os.path.join(REPO_DIR, filename))  # make file times deterministic before zipping
    zip_name = get_final_file_name(versions)
    check_call(['zip', '-D', '-X', zip_name] + file_list, cwd=REPO_DIR)

    # print hashes for debug purposes
    for file in file_list + [zip_name]:
        sha256hash = get_sha256(os.path.join(REPO_DIR, file))
        print("%s: %s" % (file, sha256hash))


def setup_android_ndk(versions):
    if os.path.isdir(NDK_DIR):
        # check that we are using the correct NDK
        from configparser import ConfigParser
        config = ConfigParser()
        with open(os.path.join(NDK_DIR, 'source.properties'), 'r') as f:
            config.read_string('[default]\n' + f.read())
            revision = config.get('default', 'Pkg.Revision')

        if revision != versions['ndk']['revision']:
            print("Existing Android NDK has unexpected revision. Deleting...")
            rmtree(NDK_DIR)

    if not os.path.isdir(NDK_DIR):
        # download Android NDK
        print("Downloading Android NDK...")
        check_call(['wget', '-c', '--no-verbose', versions['ndk']['url'], '-O', 'android-ndk.zip'])

        # check sha256 hash on downloaded file
        if get_sha256('android-ndk.zip') != versions['ndk']['sha256']:
            fail("Android NDK checksum does not match")

        # install the NDK
        print("Unpacking Android NDK...")
        ndk_dir_tmp = NDK_DIR + '-tmp'
        check_call(['unzip', '-q', 'android-ndk.zip', '-d', ndk_dir_tmp])
        content = os.listdir(ndk_dir_tmp)
        if len(content) == 1 and content[0].startswith('android-ndk-r'):
            move(os.path.join(ndk_dir_tmp, content[0]), NDK_DIR)
            os.rmdir(ndk_dir_tmp)
        else:
            fail("Could not extract NDK: %s" % str(content))

    os.putenv('ANDROID_NDK_HOME', os.path.abspath(NDK_DIR))


def prepare_tor_android_repo(versions):
    if os.path.isdir(REPO_DIR):
        # get latest commits and tags from remote
        check_call(['git', 'fetch', '--recurse-submodules=yes', 'origin'], cwd=REPO_DIR)
    else:
        # clone repo
        url = versions['tor_android_repo_url']
        check_call(['git', 'clone', '--recurse-submodules', url, REPO_DIR])

    # checkout tor-android version
    check_call(['git', 'checkout', '-f', versions['tor-android']], cwd=REPO_DIR)

    # undo all changes
    check_call(['git', 'reset', '--hard'], cwd=REPO_DIR)
    check_call(['git', 'submodule', 'foreach', 'git', 'reset', '--hard'], cwd=REPO_DIR)

    # clean all untracked files and directories (-d) from repo
    check_call(['git', 'clean', '-dffx'], cwd=REPO_DIR)
    check_call(['git', 'submodule', 'foreach', 'git', 'clean', '-dffx'], cwd=REPO_DIR)

    # check out versions of external dependencies
    checkout('tor', versions['tor'], 'external/tor')
    checkout('libevent', versions['libevent'], 'external/libevent')
    checkout('openssl', versions['openssl'], 'external/openssl')
    checkout('xz', versions['xz'], 'external/xz')
    checkout('zstd', versions['zstd'], 'external/zstd')


def checkout(name, tag, path):
    print("Checking out %s: %s" % (name, tag))
    repo_path = os.path.join(REPO_DIR, path)
    check_call(['git', 'checkout', '-f', tag], cwd=repo_path)


def build_architectures():
    # build arm pie
    os.unsetenv('APP_ABI')
    os.unsetenv('NDK_PLATFORM_LEVEL')
    os.unsetenv('PIEFLAGS')
    build_arch('tor_arm_pie.zip')

    # build arm
    os.putenv('NDK_PLATFORM_LEVEL', '14')
    os.putenv('PIEFLAGS', '')
    build_arch('tor_arm.zip')

    # build x86 pie
    os.putenv('APP_ABI', 'x86')
    os.unsetenv('NDK_PLATFORM_LEVEL')
    os.unsetenv('PIEFLAGS')
    build_arch('tor_x86_pie.zip')

    # build x86
    os.putenv('NDK_PLATFORM_LEVEL', '14')
    os.putenv('PIEFLAGS', '')
    build_arch('tor_x86.zip')


def build_arch(name):
    check_call(['make', '-C', 'external', 'clean', 'tor'], cwd=REPO_DIR)
    copy(os.path.join(REPO_DIR, 'external', 'bin', 'tor'), os.path.join(REPO_DIR, 'tor'))
    check_call(['strip', '-D', 'tor'], cwd=REPO_DIR)
    tor_path = os.path.join(REPO_DIR, 'tor')
    reset_time(tor_path)
    print("Sha256 hash of tor before zipping %s: %s" % (name, get_sha256(tor_path)))
    check_call(['zip', '-X', name, 'tor'], cwd=REPO_DIR)


def reset_time(filename):
    check_call(['touch', '--no-dereference', '-t', '197001010000.00', filename])


if __name__ == "__main__":
        main()
