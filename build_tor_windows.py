#!/usr/bin/env python3
import os
from shutil import rmtree, copy
from subprocess import check_call

import utils
from utils import REPO_DIR, EXT_DIR, reset_time

PLATFORM = "windows"


def build():
    versions, jar_name = utils.setup(PLATFORM)

    build_windows(versions)

    utils.package_geoip(versions)
    package_windows(versions, jar_name)


def build_windows(versions):
    build_windows_arch('x86_64', 'x86_64-w64-mingw32', versions)


def build_windows_arch(arch, host, versions):
    name = "tor_windows-%s.zip" % arch
    print("Building %s" % name)
    prefix_dir = os.path.abspath(os.path.join(REPO_DIR, 'prefix'))
    lib_dir = os.path.join(prefix_dir, 'lib')
    include_dir = os.path.join(prefix_dir, 'include')

    # ensure clean build environment (again here to protect against build reordering)
    utils.prepare_tor_android_repo(versions)
    if os.path.exists(prefix_dir):
        rmtree(prefix_dir)

    # create folders for static libraries
    os.mkdir(prefix_dir)
    os.mkdir(lib_dir)
    os.mkdir(include_dir)

    # setup environment
    env = os.environ.copy()

    # build zlib
    env['LDFLAGS'] = "-L%s" % prefix_dir
    env['CHOST'] = host

    zlib_dir = os.path.join(EXT_DIR, 'zlib')
    check_call(['make', '-f', 'win32/Makefile.gcc', 'BINARY_PATH=%s/bin' % prefix_dir,
                'INCLUDE_PATH=%s/include' % prefix_dir, 'LIBRARY_PATH=%s/lib' % prefix_dir,
                'SHARED_MODE=1', 'PREFIX=%s-' % host, 'install'],
               cwd=zlib_dir, env=env)

    # build libevent
    libevent_dir = os.path.join(EXT_DIR, 'libevent')

    check_call(['./autogen.sh'], cwd=libevent_dir)
    check_call(['./configure', '--disable-shared', '--prefix=%s' % prefix_dir,
                '--host=%s' % host, '--enable-static'], cwd=libevent_dir, env=env)
    check_call(['make'], cwd=libevent_dir, env=env)
    check_call(['make', 'install'], cwd=libevent_dir, env=env)

    # build openssl
    env['CFLAGS'] = "-I%s" % include_dir
    env['LDFLAGS'] = "-static -static-libgcc -L%s" % prefix_dir

    openssl_dir = os.path.join(EXT_DIR, 'openssl')
    check_call(['perl', 'Configure', '--prefix=%s' % prefix_dir,
                '--openssldir=%s' % prefix_dir, '-static', '-static-libgcc',
                '--cross-compile-prefix=%s-' % host, 'mingw64', 'no-shared', 'no-asm'],
               cwd=openssl_dir, env=env)
    check_call(['make'], cwd=openssl_dir, env=env)
    check_call(['make', 'install_sw'], cwd=openssl_dir, env=env)

    # build Tor
    tor_dir = os.path.join(EXT_DIR, 'tor')
    check_call(['./autogen.sh'], cwd=tor_dir)
    env['LIBS'] = "-lcrypt32"
    env['LDFLAGS'] = "-static -static-libgcc -L%s" % prefix_dir
    env['CFLAGS'] = "-I%s" % include_dir

    check_call(['./configure', '--disable-asciidoc', '--disable-systemd',
                '--enable-static-zlib', '--with-zlib-dir=%s' % prefix_dir,
                '--enable-static-libevent', '--with-libevent-dir=%s' % prefix_dir,
                '--enable-static-openssl', '--with-openssl-dir=%s' % prefix_dir,
                '--prefix=%s' % prefix_dir, '--host=%s' % host,
                '--disable-tool-name-check'], cwd=tor_dir, env=env)
    check_call(['make'], cwd=tor_dir, env=env)
    check_call(['make', 'install'], cwd=tor_dir, env=env)

    # copy and zip built Tor binary
    tor_path = os.path.join(REPO_DIR, 'tor')
    copy(os.path.join(prefix_dir, 'bin', 'tor.exe'), tor_path)
    check_call(['strip', '-D', 'tor'], cwd=REPO_DIR)
    reset_time(tor_path, versions)
    print("Sha256 hash of tor before zipping %s: %s" % (name, utils.get_sha256(tor_path)))
    check_call(['zip', '-X', '../' + name, 'tor'], cwd=REPO_DIR)


def package_windows(versions, jar_name):
    # zip binaries together
    file_list = ['tor_windows-x86_64.zip', 'geoip.zip']
    zip_name = utils.pack(versions, file_list, PLATFORM)

    # create POM file from template
    pom_name = utils.create_pom_file(versions, PLATFORM)

    # print hashes for debug purposes
    for file in file_list + [zip_name, jar_name, pom_name]:
        sha256hash = utils.get_sha256(file)
        print("%s: %s" % (file, sha256hash))


if __name__ == "__main__":
    build()
