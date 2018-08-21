#!/usr/bin/env python3
import os
from shutil import move, copy, rmtree, copytree
from subprocess import check_call

from utils import REPO_DIR, get_sha256, fail, get_build_versions, get_tor_version, \
    get_final_file_name, get_sources_file_name, get_pom_file_name, get_version

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

    # zip Android binaries together
    file_list = ['tor_arm_pie.zip', 'tor_arm.zip', 'tor_x86_pie.zip', 'tor_x86.zip', 'geoip.zip']
    zip_name = pack(versions, file_list, 'android')

    # zip Linux binaries together
    file_list_linux = ['tor_linux-x86_64.zip', 'geoip.zip']
    zip_name_linux = pack(versions, file_list_linux, 'linux')

    # create POM file from template
    pom_name = create_pom_file(versions, 'android')
    pom_name_linux = create_pom_file(versions, 'linux')

    # create sources jar
    jar_name = create_sources_jar(versions)
    jar_name_linux = get_sources_file_name(versions, 'linux')
    copy(os.path.join(REPO_DIR, jar_name), os.path.join(REPO_DIR, jar_name_linux))

    # print Android hashes for debug purposes
    for file in file_list + [zip_name, jar_name, pom_name]:
        sha256hash = get_sha256(os.path.join(REPO_DIR, file))
        print("%s: %s" % (file, sha256hash))

    # print Linux hashes for debug purposes
    for file in file_list_linux + [zip_name_linux, jar_name_linux, pom_name_linux]:
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
    build_linux()

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


def build_linux(name='tor_linux-x86_64.zip'):
    # create folders for static libraries
    ext_dir = os.path.abspath(os.path.join(REPO_DIR, 'external'))
    lib_dir = os.path.join(ext_dir, 'lib')
    if not os.path.exists(lib_dir):
        os.mkdir(lib_dir)
    include_dir = os.path.join(ext_dir, 'include')
    if not os.path.exists(include_dir):
        os.mkdir(include_dir)

    # setup environment
    env = os.environ.copy()
    env['LDFLAGS'] = "-L%s" % ext_dir
    env['CFLAGS'] = "-fPIC -I%s" % include_dir
    env['LIBS'] = "-L%s" % lib_dir
    env['PKG_PATH'] = include_dir

    # ensure clean build environment
    check_call(['git', 'submodule', 'foreach', 'git', 'clean', '-dffx'], cwd=REPO_DIR)

    # build lzma
    xz_dir = os.path.join(ext_dir, 'xz')
    check_call(['./autogen.sh'], cwd=xz_dir)
    check_call(['./configure', '--disable-shared', '--enable-static', '--disable-doc',
                '--disable-xz', '--disable-xzdec', '--disable-lzmadec', '--disable-lzmainfo',
                '--disable-lzma-links', '--disable-scripts', '--prefix=%s' % ext_dir],
               cwd=xz_dir, env=env)
    check_call(['make', 'install'], cwd=xz_dir)

    # build zstd
    zstd_dir = os.path.join(ext_dir, 'zstd', 'lib')
    check_call(['make', 'libzstd.a-mt'], cwd=zstd_dir)
    check_call(['make', 'libzstd.pc'], cwd=zstd_dir)
    copy(os.path.join(zstd_dir, 'libzstd.a'), lib_dir)
    copy(os.path.join(zstd_dir, 'libzstd.pc'), os.path.join(lib_dir, 'pkgconfig'))
    copy(os.path.join(zstd_dir, 'zstd.h'), include_dir)
    copy(os.path.join(zstd_dir, 'common', 'zstd_errors.h'), include_dir)
    copy(os.path.join(zstd_dir, 'deprecated', 'zbuff.h'), include_dir)
    copy(os.path.join(zstd_dir, 'dictBuilder', 'zdict.h'), include_dir)

    # build openssl
    openssl_dir = os.path.join(ext_dir, 'openssl')
    check_call(['perl', 'Configure', 'linux-x86_64', '-fPIC'], cwd=openssl_dir, env=env)
    check_call(['make', 'depend'], cwd=openssl_dir)
    check_call(['make', 'build_libs'], cwd=openssl_dir)
    copy(os.path.join(openssl_dir, 'libcrypto.a'), os.path.join(lib_dir, 'libcrypto.a'))
    copy(os.path.join(openssl_dir, 'libssl.a'), os.path.join(lib_dir, 'libssl.a'))
    copytree(os.path.join(openssl_dir, 'include', 'openssl'), os.path.join(include_dir, 'openssl'))

    # build libevent
    libevent_dir = os.path.join(REPO_DIR, 'external', 'libevent')
    check_call(['./autogen.sh'], cwd=libevent_dir)
    check_call(['./configure', '--disable-shared'], cwd=libevent_dir, env=env)
    check_call(['make', './include/event2/event-config.h', 'all-am'], cwd=libevent_dir)
    copy(os.path.join(libevent_dir, '.libs', 'libevent.a'), os.path.join(lib_dir, 'libevent.a'))
    copytree(os.path.join(libevent_dir, 'include', 'event2'), os.path.join(include_dir, 'event2'))

    # build Tor
    tor_dir = os.path.join(REPO_DIR, 'external', 'tor')
    check_call(['./autogen.sh'], cwd=tor_dir)
    env['CFLAGS'] += ' -O3'  # needed for FORTIFY_SOURCE
    check_call(['./configure', '--disable-asciidoc', '--disable-systemd',
                '--enable-static-libevent', '--with-libevent-dir=%s' % ext_dir,
                '--enable-static-openssl', '--with-openssl-dir=%s' % ext_dir], cwd=tor_dir, env=env)
    check_call(['make', 'all-am'], cwd=tor_dir)

    # copy and zip built Tor binary
    tor_path = os.path.join(REPO_DIR, 'tor')
    copy(os.path.join(tor_dir, 'src', 'or', 'tor'), tor_path)
    check_call(['strip', '-D', 'tor'], cwd=REPO_DIR)
    reset_time(tor_path)
    print("Sha256 hash of tor before zipping %s: %s" % (name, get_sha256(tor_path)))
    check_call(['zip', '-X', name, 'tor'], cwd=REPO_DIR)


def pack(versions, file_list, platform):
    for filename in file_list:
        reset_time(os.path.join(REPO_DIR, filename))  # make file times deterministic before zipping
    zip_name = get_final_file_name(versions, platform)
    check_call(['zip', '-D', '-X', zip_name] + file_list, cwd=REPO_DIR)
    return zip_name


def reset_time(filename):
    check_call(['touch', '--no-dereference', '-t', '197001010000.00', filename])


def create_sources_jar(versions):
    external_dir = os.path.join(REPO_DIR, 'external')
    check_call(['git', 'clean', '-dfx'], cwd=external_dir)
    jar_files = []
    for root, dir_names, filenames in os.walk(external_dir):
        for f in filenames:
            jar_files.append(os.path.join(root, f))
    for file in jar_files:
        reset_time(file)
    jar_name = get_sources_file_name(versions)
    jar_path = os.path.abspath(os.path.join(REPO_DIR, jar_name))
    rel_paths = [os.path.relpath(f, external_dir) for f in sorted(jar_files)]
    check_call(['jar', 'cf', jar_path] + rel_paths, cwd=external_dir)
    return jar_name


def create_pom_file(versions, platform='android'):
    tor_version = get_tor_version(versions)
    pom_name = get_pom_file_name(versions, platform)
    if platform == 'android':
        template = 'template.pom'
    elif platform == 'linux':
        template = 'template-linux.pom'
    else:
        raise RuntimeError("Unknown platform: %s" % platform)
    with open(template, 'rt') as infile:
        with open(os.path.join(REPO_DIR, pom_name), 'wt') as outfile:
            for line in infile:
                outfile.write(line.replace('VERSION', tor_version))
    return pom_name


if __name__ == "__main__":
    main()
