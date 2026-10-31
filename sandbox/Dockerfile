FROM docker:dind

# Install standard developer utilities & inspection tools in the sandbox
RUN apk add --no-cache \
    bash \
    curl \
    wget \
    git \
    jq \
    coreutils \
    nano \
    vim \
    grep \
    sed \
    gawk \
    net-tools \
    iproute2 \
    lsof \
    htop \
    procps \
    tar \
    tree \
    util-linux

WORKDIR /workspace

# Preserve DinD entrypoint and keep container alive
CMD ["sh", "-c", "dockerd-entrypoint.sh & while ! docker info >/dev/null 2>&1; do sleep 0.5; done; echo 'Docker-in-Docker sandbox ready!'; exec sleep infinity"]
