#!/usr/bin/env python3
import os
from shutil import rmtree, copy
from subprocess import check_call

import utils
from utils import BUILD_DIR, OUTPUT_DIR, TOR_CONFIGURE_FLAGS, OPENSSL_CONFIGURE_FLAGS, REPRODUCIBLE_GCC_CFLAGS, \
    XZ_CONFIGURE_FLAGS, reset_time, get_sha256, pack, create_pom_file

PLATFORM = "linux"


def build():
    versions, jar_name = utils.setup(PLATFORM)

    build_linux(versions)

    utils.package_geoip(versions)
    package_linux(versions, jar_name)


def build_linux(versions):
    build_linux_arch('aarch64', 'armv8-a', 'aarch64-linux-gnu-gcc', 'linux-aarch64', 'aarch64', versions)
    build_linux_arch('armhf', 'armv7-a', 'arm-linux-gnueabihf-gcc', 'linux-armv4', 'arm-linux-gnueabihf', versions)
    build_linux_arch('x86_64', 'x86-64', 'x86_64-linux-gnu-gcc', 'linux-x86_64', 'x86_64', versions)


def build_linux_arch(arch, gcc_arch, cc_env, openssl_target, autogen_host, versions):
    name = "tor_linux-%s.zip" % arch
    print("Building %s" % name)
    prefix_dir = os.path.abspath(os.path.join(BUILD_DIR, 'prefix'))
    lib_dir = os.path.join(prefix_dir, 'lib')
    include_dir = os.path.join(prefix_dir, 'include')

    # ensure clean build environment (again here to protect against build reordering)
    utils.prepare_repos(versions)
    if os.path.exists(prefix_dir):
        rmtree(prefix_dir)

    # create folders for static libraries
    os.mkdir(prefix_dir)
    os.mkdir(lib_dir)
    os.mkdir(include_dir)

    # setup environment
    env = os.environ.copy()
    env['SOURCE_DATE_EPOCH'] = "1234567890"
    env['LDFLAGS'] = "-L%s" % lib_dir
    env['LD_LIBRARY_PATH'] = lib_dir
    env['CFLAGS'] = REPRODUCIBLE_GCC_CFLAGS + ' -fPIC -I%s' % include_dir
    env['PKG_CONFIG_PATH'] = os.path.join(lib_dir, 'pkgconfig')
    env['LIBS'] = "-ldl -L%s" % lib_dir
    env['CC'] = cc_env

    # build lzma
    xz_dir = os.path.join(BUILD_DIR, 'xz')
    check_call(['./autogen.sh'], cwd=xz_dir)
    check_call(['./configure',
                '--prefix=%s' % prefix_dir,
                '--host=%s' % autogen_host,
                ] + XZ_CONFIGURE_FLAGS, cwd=xz_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count()), 'install'], cwd=xz_dir, env=env)

    # build zstd
    zstd_dir = os.path.join(BUILD_DIR, 'zstd', "lib")
    check_call(['make', '-j', str(os.cpu_count()), 'DESTDIR=%s' % prefix_dir, 'PREFIX=""', 'install'],
               cwd=zstd_dir, env=env)

    # build zlib
    zlib_dir = os.path.join(BUILD_DIR, 'zlib')
    check_call(['./configure', '--prefix=%s' % prefix_dir], cwd=zlib_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count()), 'install'], cwd=zlib_dir, env=env)

    # build openssl
    openssl_dir = os.path.join(BUILD_DIR, 'openssl')
    extra_flags = []
    if autogen_host.endswith("64"):
        extra_flags = ['enable-ec_nistp_64_gcc_128']
    check_call(['perl', 'Configure',
                '--prefix=%s' % prefix_dir,
                '--openssldir=%s' % prefix_dir,
                '-march=%s' % gcc_arch,
                openssl_target,
                'shared',
                ] + OPENSSL_CONFIGURE_FLAGS + extra_flags, cwd=openssl_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count())], cwd=openssl_dir, env=env)
    check_call(['make', 'install_sw'], cwd=openssl_dir, env=env)

    # build libevent
    libevent_dir = os.path.join(BUILD_DIR, 'libevent')
    check_call(['./autogen.sh'], cwd=libevent_dir)
    check_call(['./configure', '--disable-shared', '--prefix=%s' % prefix_dir,
                '--host=%s' % autogen_host], cwd=libevent_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count())], cwd=libevent_dir, env=env)
    check_call(['make', 'install'], cwd=libevent_dir, env=env)

    # build Tor
    tor_dir = os.path.join(BUILD_DIR, 'tor')
    check_call(['./autogen.sh'], cwd=tor_dir)
    env['CFLAGS'] += ' -O3'  # needed for FORTIFY_SOURCE
    check_call(['./configure',
                '--host=%s' % autogen_host,
                '--prefix=%s' % prefix_dir,
                '--enable-static-tor',
                '--enable-lzma',
                '--enable-zstd',
                '--enable-static-zlib',
                '--with-zlib-dir=%s' % prefix_dir,
                '--enable-static-libevent',
                '--with-libevent-dir=%s' % prefix_dir,
                '--enable-static-openssl',
                '--with-openssl-dir=%s' % prefix_dir,
                ] + TOR_CONFIGURE_FLAGS, cwd=tor_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count()), 'install'], cwd=tor_dir, env=env)

    # copy and zip built Tor binary
    tor_path = os.path.join(OUTPUT_DIR, 'tor')
    copy(os.path.join(BUILD_DIR, 'tor', 'src', 'app', 'tor'), tor_path)
    check_call(['strip', '-D', '--strip-unneeded', '--strip-debug', '-R', '.note*', '-R', '.comment', tor_path])
    reset_time(tor_path, versions)
    print("Sha256 hash of tor before zipping %s: %s" % (name, get_sha256(tor_path)))
    check_call(['zip', '--no-dir-entries', '--junk-paths', '-X', name, 'tor'], cwd=OUTPUT_DIR)


def package_linux(versions, jar_name):
    # zip binaries together
    file_list = [
        os.path.join(OUTPUT_DIR, 'tor_linux-aarch64.zip'),
        os.path.join(OUTPUT_DIR, 'tor_linux-armhf.zip'),
        os.path.join(OUTPUT_DIR, 'tor_linux-x86_64.zip'),
        os.path.join(OUTPUT_DIR, 'geoip.zip'),
    ]
    zip_name = pack(versions, file_list, PLATFORM)

    # create POM file from template
    pom_name = create_pom_file(versions, PLATFORM)

    # print hashes for debug purposes
    for file in file_list + [zip_name, jar_name, pom_name]:
        sha256hash = get_sha256(file)
        print("%s: %s" % (file, sha256hash))


if __name__ == "__main__":
    build()
