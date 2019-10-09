#!/usr/bin/env python3
import os
from shutil import move, copy, rmtree
from subprocess import check_call

from utils import REPO_DIR, get_sha256, fail, get_build_versions, get_version_tag, \
    get_final_file_name, get_sources_file_name, get_pom_file_name, get_version

ZLIB_REPO_URL = 'https://github.com/madler/zlib.git'
NDK_DIR = 'android-ndk'
EXT_DIR = os.path.abspath(os.path.join(REPO_DIR, 'external'))


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

    # create sources jar before building
    jar_name = create_sources_jar(versions)

    # build Tor for various platforms and architectures
    build()
    build_android()

    # zip geoip database
    geoip_path = os.path.join(REPO_DIR, 'geoip')
    copy(os.path.join(EXT_DIR, 'tor', 'src', 'config', 'geoip'), geoip_path)
    reset_time(geoip_path)
    check_call(['zip', '-X', '../geoip.zip', 'geoip'], cwd=REPO_DIR)

    # zip binaries together
    file_list = ['tor_linux-x86_64.zip', 'geoip.zip']
    zip_name = pack(versions, file_list)
    # zip Android binaries together
    file_list_android = ['tor_arm.zip', 'tor_arm_pie.zip', 'tor_arm64_pie.zip',
                         'tor_x86.zip', 'tor_x86_pie.zip', 'tor_x86_64_pie.zip',
                         'geoip.zip']
    zip_name_android = pack(versions, file_list_android, android=True)

    # create POM file from template
    pom_name = create_pom_file(versions)
    pom_name_android = create_pom_file(versions, android=True)

    # print hashes for debug purposes
    for file in file_list + [zip_name, jar_name, pom_name]:
        sha256hash = get_sha256(file)
        print("%s: %s" % (file, sha256hash))
    print("Android:")
    for file in file_list_android + [zip_name_android, pom_name_android]:
        sha256hash = get_sha256(file)
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

    os.environ['ANDROID_NDK_HOME'] = os.path.abspath(NDK_DIR)


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
    check_call(['git', 'submodule', 'update', '--init', '--recursive'], cwd=REPO_DIR)

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


def checkout(name, tag, path):
    print("Checking out %s: %s" % (name, tag))
    repo_path = os.path.join(EXT_DIR, path)
    check_call(['git', 'checkout', '-f', tag], cwd=repo_path)


def build_android():
    os.environ.pop("PIEFLAGS", None)  # uses default PIE flags, if not present

    # build arm
    env = os.environ.copy()
    env['APP_ABI'] = "armeabi-v7a"
    env['NDK_PLATFORM_LEVEL'] = "14"
    env['PIEFLAGS'] = ""  # do not use default PIE flags
    build_android_arch('tor_arm.zip', env)

    # build arm pie
    env = os.environ.copy()
    env['APP_ABI'] = "armeabi-v7a"
    env['NDK_PLATFORM_LEVEL'] = "16"  # first level supporting PIE
    build_android_arch('tor_arm_pie.zip', env)

    # build arm64 pie
    env = os.environ.copy()
    env['APP_ABI'] = "arm64-v8a"
    env['NDK_PLATFORM_LEVEL'] = "21"  # first level supporting 64-bit
    build_android_arch('tor_arm64_pie.zip', env)

    # build x86
    env = os.environ.copy()
    env['APP_ABI'] = "x86"
    env['NDK_PLATFORM_LEVEL'] = "14"
    env['PIEFLAGS'] = ""  # do not use default PIE flags
    build_android_arch('tor_x86.zip', env)

    # build x86 pie
    env = os.environ.copy()
    env['APP_ABI'] = "x86"
    env['NDK_PLATFORM_LEVEL'] = "16"  # first level supporting PIE
    build_android_arch('tor_x86_pie.zip', env)

    # build x86_64 pie
    env = os.environ.copy()
    env['APP_ABI'] = "x86_64"
    env['NDK_PLATFORM_LEVEL'] = "21"  # first level supporting 64-bit
    build_android_arch('tor_x86_64_pie.zip', env)


def build_android_arch(name, env):
    print("Building %s" % name)
    check_call(['make', '-C', 'external', 'clean', 'tor'], cwd=REPO_DIR, env=env)
    copy(os.path.join(EXT_DIR, 'bin', 'tor'), os.path.join(REPO_DIR, 'tor'))
    check_call(['strip', '-D', 'tor'], cwd=REPO_DIR)
    tor_path = os.path.join(REPO_DIR, 'tor')
    reset_time(tor_path)
    print("Sha256 hash of tor before zipping %s: %s" % (name, get_sha256(tor_path)))
    check_call(['zip', '-X', '../' + name, 'tor'], cwd=REPO_DIR)


def build(name='tor_linux-x86_64.zip'):
    prefix_dir = os.path.abspath(os.path.join(REPO_DIR, 'prefix'))
    lib_dir = os.path.join(prefix_dir, 'lib')
    include_dir = os.path.join(prefix_dir, 'include')

    # ensure clean build environment (again here to protect against build reordering)
    check_call(['git', 'submodule', 'foreach', 'git', 'clean', '-dffx'], cwd=REPO_DIR)
    if os.path.exists(prefix_dir):
        rmtree(prefix_dir)

    # create folders for static libraries
    os.mkdir(prefix_dir)
    os.mkdir(lib_dir)
    os.mkdir(include_dir)

    # setup environment
    env = os.environ.copy()
    env['LDFLAGS'] = "-L%s" % prefix_dir
    env['CFLAGS'] = "-fPIC -I%s" % include_dir
    env['LIBS'] = "-L%s" % lib_dir

    # build zlib
    zlib_dir = os.path.join(EXT_DIR, 'zlib')
    check_call(['./configure', '--prefix=%s' % prefix_dir], cwd=zlib_dir, env=env)
    check_call(['make', 'install'], cwd=zlib_dir, env=env)

    # build openssl
    openssl_dir = os.path.join(EXT_DIR, 'openssl')
    check_call(['./config', '--prefix=%s' % prefix_dir], cwd=openssl_dir, env=env)
    check_call(['make'], cwd=openssl_dir, env=env)
    check_call(['make', 'install_sw'], cwd=openssl_dir, env=env)

    # build libevent
    libevent_dir = os.path.join(EXT_DIR, 'libevent')
    check_call(['./autogen.sh'], cwd=libevent_dir)
    check_call(['./configure', '--disable-shared', '--prefix=%s' % prefix_dir], cwd=libevent_dir,
               env=env)
    check_call(['make'], cwd=libevent_dir, env=env)
    check_call(['make', 'install'], cwd=libevent_dir, env=env)

    # build Tor
    tor_dir = os.path.join(EXT_DIR, 'tor')
    check_call(['./autogen.sh'], cwd=tor_dir)
    env['CFLAGS'] += ' -O3'  # needed for FORTIFY_SOURCE
    check_call(['./configure', '--disable-asciidoc', '--disable-systemd',
                '--enable-static-zlib', '--with-zlib-dir=%s' % prefix_dir,
                '--enable-static-libevent', '--with-libevent-dir=%s' % prefix_dir,
                '--enable-static-openssl', '--with-openssl-dir=%s' % prefix_dir,
                '--prefix=%s' % prefix_dir], cwd=tor_dir, env=env)
    check_call(['make', 'install'], cwd=tor_dir, env=env)

    # copy and zip built Tor binary
    tor_path = os.path.join(REPO_DIR, 'tor')
    copy(os.path.join(prefix_dir, 'bin', 'tor'), tor_path)
    check_call(['strip', '-D', 'tor'], cwd=REPO_DIR)
    reset_time(tor_path)
    print("Sha256 hash of tor before zipping %s: %s" % (name, get_sha256(tor_path)))
    check_call(['zip', '-X', '../' + name, 'tor'], cwd=REPO_DIR)


def pack(versions, file_list, android=False):
    for filename in file_list:
        reset_time(filename)  # make file times deterministic before zipping
    zip_name = get_final_file_name(versions, android)
    check_call(['zip', '-D', '-X', zip_name] + file_list)
    return zip_name


def reset_time(filename):
    check_call(['touch', '--no-dereference', '-t', '197001010000.00', filename])


def create_sources_jar(versions):
    jar_files = []
    for root, dir_names, filenames in os.walk(EXT_DIR):
        for f in filenames:
            if '/.git' in root:
                continue
            jar_files.append(os.path.join(root, f))
    for file in jar_files:
        reset_time(file)
    jar_name = get_sources_file_name(versions)
    jar_path = os.path.abspath(jar_name)
    rel_paths = [os.path.relpath(f, EXT_DIR) for f in sorted(jar_files)]
    check_call(['jar', 'cf', jar_path] + rel_paths, cwd=EXT_DIR)
    return jar_name


def create_pom_file(versions, android=False):
    version = get_version_tag(versions)
    pom_name = get_pom_file_name(versions, android)
    template = 'template-android.pom' if android else 'template.pom'
    with open(template, 'rt') as infile:
        with open(pom_name, 'wt') as outfile:
            for line in infile:
                outfile.write(line.replace('VERSION', version))
    return pom_name


if __name__ == "__main__":
    main()
