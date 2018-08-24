# Tor Reproducer

This is a tool you can use to verify that the version of Tor
used by [Briar](https://briar.app) was built exactly from the public source code
and no modifications (such as backdoors) were made.

More information about these so called reproducible builds is available at
[reproducible-builds.org](https://reproducible-builds.org/).

The source code for this tool is available at
https://code.briarproject.org/briar/tor-reproducer

## How to use

Make sure the version of Tor you want to verify is included in `tor-versions.json`.

Verify that you have `docker` installed:

    docker --version

If this command does not work,
please [install Docker](https://docs.docker.com/install/)
and continue once it is installed.

### Using our pre-built image

If you trust that our pre-built Docker image was build exactly from *its* source,
you can use it for faster verification.
If not, you can read the next section to learn how to build the image yourself.
Then you are only trusting the official `debian:stable` which is out of our control.

Otherwise, you can skip the next section and move directly to *Run the verification*.

### Building your own image

Check out the source repository:

    git clone https://code.briarproject.org/briar/tor-reproducer.git

Build our Docker image:

    docker build -t briar/tor-reproducer tor-reproducer

### Run the verification

To verify a specific version of Tor for Android, run

    docker run briar/tor-reproducer:latest ./verify-tor.py [version]

Where `[version]` is the version of Tor you want to test, for example `0.3.3.6`.

You can find a list of versions in Tor's
[source code repository](https://gitweb.torproject.org/tor.git/refs/).
Just remove the `tor-` from `tor-0.3.3.6`.

If you leave out `[version]` it will build the latest version
that was registered in `tor-versions.json`.

In case there is an issue with the verification of an old build,
this *might* be caused by an update of the container.
You can try to use the original container by running:

    docker run briar/tor-reproducer:[version] ./build-tor.py [version]

There should be a tag with the name `[version]` in this repository
that you could be used to reproduce the old container.
Note that this will not work if the issue is caused by an updated Debian package.

### Only build Tor

To build a specific version of Tor for Android, run

    docker run briar/tor-reproducer:latest ./verify-tor.py [version]