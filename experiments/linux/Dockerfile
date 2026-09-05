# Build separately with --platform linux/arm64 and --platform linux/amd64.
# Record the resulting image ID with validation output: package versions track
# the signed Ubuntu 24.04 repositories available at image-build time.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       clang lld make python3 zsh gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
# clang's sanitizer runtime is only a recommended package on this distro.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libclang-rt-18-dev \
    && rm -rf /var/lib/apt/lists/*
