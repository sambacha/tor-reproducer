#!/usr/bin/env python3
import os
from shutil import rmtree, copy
from subprocess import check_call

import utils
from utils import BUILD_DIR, get_output_dir, TOR_CONFIGURE_FLAGS, OPENSSL_CONFIGURE_FLAGS, REPRODUCIBLE_GCC_CFLAGS, \
    XZ_CONFIGURE_FLAGS, reset_time, get_sha256

PLATFORM = "windows"


def build():
    versions, jar_name = utils.setup(PLATFORM)

    build_windows(versions)

    package_windows(versions, jar_name)


def build_windows(versions):
    build_windows_arch('x86_64', 'x86_64-w64-mingw32', versions)


def build_windows_arch(arch, host, versions):
    name = "tor_windows-%s.zip" % arch
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
    env['LDFLAGS'] = "-L%s" % prefix_dir
    env['CFLAGS'] = REPRODUCIBLE_GCC_CFLAGS + ' -fPIC -I%s' % include_dir
    env['PKG_CONFIG_PATH'] = os.path.join(lib_dir, 'pkgconfig')  # needed to find OpenSSL
    env['CHOST'] = host

    # build lzma
    xz_dir = os.path.join(BUILD_DIR, 'xz')
    check_call(['./autogen.sh'], cwd=xz_dir)
    check_call(['./configure',
                '--prefix=%s' % prefix_dir,
                '--host=%s' % host,
                ] + XZ_CONFIGURE_FLAGS, cwd=xz_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count()), 'install'], cwd=xz_dir, env=env)

    # build zlib
    zlib_dir = os.path.join(BUILD_DIR, 'zlib')
    check_call(['make', '-j', str(os.cpu_count()), '-f', 'win32/Makefile.gcc', 'BINARY_PATH=%s/bin' % prefix_dir,
                'INCLUDE_PATH=%s/include' % prefix_dir, 'LIBRARY_PATH=%s/lib' % prefix_dir,
                'SHARED_MODE=1', 'PREFIX=%s-' % host, 'install'],
               cwd=zlib_dir, env=env)

    # build openssl
    env['LDFLAGS'] = REPRODUCIBLE_GCC_CFLAGS + " -static -static-libgcc -L%s" % prefix_dir

    openssl_dir = os.path.join(BUILD_DIR, 'openssl')
    check_call(['perl', 'Configure',
                'mingw64',
                '--cross-compile-prefix=%s-' % host,
                '--prefix=%s' % prefix_dir,
                '--openssldir=%s' % prefix_dir,
                # '-static',  # https://github.com/openssl/openssl/issues/14574
                '-static-libgcc',
                'no-shared',
                'enable-ec_nistp_64_gcc_128',
                ] + OPENSSL_CONFIGURE_FLAGS, cwd=openssl_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count())], cwd=openssl_dir, env=env)
    check_call(['make', 'install_sw'], cwd=openssl_dir, env=env)

    # build libevent
    libevent_dir = os.path.join(BUILD_DIR, 'libevent')
    check_call(['./autogen.sh'], cwd=libevent_dir)
    check_call(['./configure',
                '--host=%s' % host,
                '--disable-libevent-regress',
                '--disable-samples',
                '--disable-shared',
                '--prefix=%s' % prefix_dir,
                ], cwd=libevent_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count())], cwd=libevent_dir, env=env)
    check_call(['make', 'install'], cwd=libevent_dir, env=env)

    # build Tor
    tor_dir = os.path.join(BUILD_DIR, 'tor')
    check_call(['./autogen.sh'], cwd=tor_dir)
    env['CFLAGS'] += ' -O3'
    env['LIBS'] = "-lcrypt32"

    # TODO check if a completely static Tor is still portable
    #  '--enable-static-tor',
    check_call(['./configure',
                '--host=%s' % host,
                '--prefix=%s' % prefix_dir,
                '--enable-lzma',
                '--enable-static-zlib',
                '--with-zlib-dir=%s' % prefix_dir,
                '--enable-static-libevent',
                '--with-libevent-dir=%s' % prefix_dir,
                '--enable-static-openssl',
                '--with-openssl-dir=%s' % prefix_dir,
                ] + TOR_CONFIGURE_FLAGS, cwd=tor_dir, env=env)
    check_call(['make', '-j', str(os.cpu_count())], cwd=tor_dir, env=env)
    check_call(['make', 'install'], cwd=tor_dir, env=env)

    # copy and zip built Tor binary
    output_dir = get_output_dir(PLATFORM)
    tor_path = os.path.join(output_dir, 'tor')
    copy(os.path.join(prefix_dir, 'bin', 'tor.exe'), tor_path)
    check_call(['strip', '-D', '--strip-unneeded', '--strip-debug', '-R', '.note*', '-R', '.comment', tor_path])
    reset_time(tor_path, versions)
    print("Sha256 hash of tor before zipping %s: %s" % (name, get_sha256(tor_path)))
    check_call(['zip', '--no-dir-entries', '--junk-paths', '-X', name, 'tor'], cwd=output_dir)


def package_windows(versions, jar_name):
    # zip binaries together
    output_dir = get_output_dir(PLATFORM)
    file_list = [
        os.path.join(output_dir, 'tor_windows-x86_64.zip'),
    ]
    zip_name = utils.pack(versions, file_list, PLATFORM)
    pom_name = utils.create_pom_file(versions, PLATFORM)
    print("%s:" % PLATFORM)
    for file in file_list + [zip_name, jar_name, pom_name]:
        sha256hash = utils.get_sha256(file)
        print("%s: %s" % (file, sha256hash))


if __name__ == "__main__":
    build()
