FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git tar xz-utils unzip locales procps iproute2 util-linux \
    libicu74 libssl3t64 libsqlite3-0 libbz2-1.0 libffi8 liblzma5 \
    libreadline8t64 libncursesw6 libgssapi-krb5-2 libgomp1 zlib1g && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/actions-runner /opt/hostedtoolcache/Python/3.13.15/x64 /opt/node && \
    curl -fsSL https://github.com/actions/runner/releases/download/v2.338.0/actions-runner-linux-x64-2.338.0.tar.gz -o /tmp/runner.tgz && \
    echo 'af4b794c1bc41d73d40535e3fe092a39f9679cd8d965954c2aca25a05ca41d32  /tmp/runner.tgz' | sha256sum -c - && \
    tar -xzf /tmp/runner.tgz -C /opt/actions-runner && \
    curl -fsSL https://github.com/actions/python-versions/releases/download/3.13.15-31064747964/python-3.13.15-linux-24.04-x64.tar.gz -o /tmp/python.tgz && \
    echo '4e544242f8a4ef647a6f511b67f9b00eefc9ef366644e3c40a27a6eff709ae2b  /tmp/python.tgz' | sha256sum -c - && \
    tar -xzf /tmp/python.tgz -C /opt/hostedtoolcache/Python/3.13.15/x64 && \
    curl -fsSL https://nodejs.org/dist/v22.16.0/node-v22.16.0-linux-x64.tar.xz -o /tmp/node.txz && \
    echo 'f4cb75bb036f0d0eddf6b79d9596df1aaab9ddccd6a20bf489be5abe9467e84e  /tmp/node.txz' | sha256sum -c - && \
    tar -xJf /tmp/node.txz -C /opt/node --strip-components=1 && \
    rm /tmp/runner.tgz /tmp/python.tgz /tmp/node.txz

ENV PATH="/opt/hostedtoolcache/Python/3.13.15/x64/bin:/opt/node/bin:${PATH}" \
    LD_LIBRARY_PATH=/opt/hostedtoolcache/Python/3.13.15/x64/lib \
    HOME=/workspace/home
COPY requirements-ci.lock /opt/requirements-ci.lock
RUN python -m pip download --require-hashes -r /opt/requirements-ci.lock -d /opt/wheels && \
    useradd --uid 1001 --create-home --shell /bin/bash ci && \
    mkdir -p /workspace /runner && chown ci:ci /workspace /runner
COPY tools/ci/runner-entrypoint.sh /opt/runner-entrypoint.sh
USER 1001:1001
WORKDIR /runner
ENTRYPOINT ["bash", "/opt/runner-entrypoint.sh"]
