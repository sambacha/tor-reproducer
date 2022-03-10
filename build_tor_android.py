#!/usr/bin/env python3
import os
from shutil import rmtree, move, copy
from subprocess import check_call

import utils
from utils import get_sha256, fail, BUILD_DIR, get_output_dir, reset_time

NDK_DIR = 'android-ndk'
PLATFORM = "android"


def build():
    versions, jar_name = utils.setup(PLATFORM)

    setup_android_ndk(versions)

    build_android(versions)

    package_android(versions, jar_name)


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

    os.environ['ANDROID_NDK_HOME'] = os.path.abspath(NDK_DIR)


def build_android(versions):
    # apply tor-android patches first
    apply_tor_patch("6522c8a2ae9b2f9c4c488188f88d38728ee487a7")
    apply_tor_patch("fbd64bbed2848eb17c559a4c599a6834eb7db33a")

    # use default PIE flags, if not present
    os.environ.pop("PIEFLAGS", None)

    # build arm pie
    env = os.environ.copy()
    env['APP_ABI'] = "armeabi-v7a"
    env['NDK_PLATFORM_LEVEL'] = "16"  # first level supporting PIE
    build_android_arch('tor_arm_pie.zip', env, versions)

    # build arm64 pie
    env = os.environ.copy()
    env['APP_ABI'] = "arm64-v8a"
    env['NDK_PLATFORM_LEVEL'] = "21"  # first level supporting 64-bit
    build_android_arch('tor_arm64_pie.zip', env, versions)

    # build x86 pie
    env = os.environ.copy()
    env['APP_ABI'] = "x86"
    env['NDK_PLATFORM_LEVEL'] = "16"  # first level supporting PIE
    build_android_arch('tor_x86_pie.zip', env, versions)

    # build x86_64 pie
    env = os.environ.copy()
    env['APP_ABI'] = "x86_64"
    env['NDK_PLATFORM_LEVEL'] = "21"  # first level supporting 64-bit
    build_android_arch('tor_x86_64_pie.zip', env, versions)


def build_android_arch(name, env, versions):
    print("Building %s" % name)
    output_dir = get_output_dir(PLATFORM)
    # TODO add extra flags to configure?
    #  '--enable-static-tor',
    #  '--enable-static-zlib',
    check_call(['make', 'clean', 'tor'], cwd=BUILD_DIR, env=env)
    tor_path = os.path.join(output_dir, 'tor')
    # note: stripping happens in makefile for now
    copy(os.path.join(BUILD_DIR, 'tor', 'src', 'app', 'tor'), tor_path)
    reset_time(tor_path, versions)
    print("Sha256 hash of tor before zipping %s: %s" % (name, get_sha256(tor_path)))
    check_call(['zip', '--no-dir-entries', '--junk-paths', '-X', name, 'tor'], cwd=output_dir)


def apply_tor_patch(commit):
    tor_path = os.path.join(BUILD_DIR, 'tor')
    check_call(['wget', '--no-verbose', 'https://github.com/guardianproject/tor/commit/' + commit + '.patch'],
               cwd=tor_path)
    check_call(['git', 'apply', commit + '.patch'], cwd=tor_path)


def package_android(versions, jar_name):
    # zip binaries together
    output_dir = get_output_dir(PLATFORM)
    file_list = [
        os.path.join(output_dir, 'tor_arm_pie.zip'),
        os.path.join(output_dir, 'tor_arm64_pie.zip'),
        os.path.join(output_dir, 'tor_x86_pie.zip'),
        os.path.join(output_dir, 'tor_x86_64_pie.zip'),
    ]
    zip_name = utils.pack(versions, file_list, PLATFORM)
    pom_name = utils.create_pom_file(versions, PLATFORM)
    print("%s:" % PLATFORM)
    for file in file_list + [zip_name, jar_name, pom_name]:
        sha256hash = get_sha256(file)
        print("%s: %s" % (file, sha256hash))


if __name__ == "__main__":
    build()
