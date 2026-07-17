ARG GO_VERSION=1.26.5
ARG GO_IMAGE_DIGEST=sha256:1ecb7edf62a0408027bd5729dfd6b1b8766e578e8df93995b225dfd0944eb651

FROM --platform=$BUILDPLATFORM golang:${GO_VERSION}-bookworm@${GO_IMAGE_DIGEST} AS tool-builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG TARGETARCH

ARG TERRAFORM_DOCS_VERSION=0.24.0
ARG TERRAFORM_DOCS_COMMIT=9d4455198941806aa02ec14369de030cda2c2b59
ARG TERRAFORM_DOCS_SOURCE_SHA256=6080fe612002149187d47ca1a23021d277822b0cfba71536c13bbcf22003ecc7

ARG TFLINT_VERSION=0.63.1
ARG TFLINT_COMMIT=cd0cce4fa3decaabba3c0667c235651ac06a4221
ARG TFLINT_SOURCE_SHA256=8d9b5aeba7b82640fa21f80d2f490180ed72232f0158cd1e04e91260a41be1a9

ARG TRIVY_VERSION=0.72.0
ARG TRIVY_COMMIT=8a32853686209a428179bb3a1688802b25691564
ARG TRIVY_SOURCE_SHA256=5a922c388846d11345ce8283e4373be312458f002abc667c3cd1f77c43163725

ARG FZF_VERSION=0.74.0
ARG FZF_COMMIT=6765f464a60e39afc20775f54f7ba40896bf1b81
ARG FZF_SOURCE_SHA256=e537d3834d1927cec96c630aea6c6813bbe60b83c453314dcfb9f58285a8bd0b

COPY scripts/download-and-verify /usr/local/bin/download-and-verify
COPY scripts/build-go-tools /usr/local/bin/build-go-tools

RUN --mount=type=cache,target=/go/pkg/mod,sharing=locked \
    --mount=type=cache,target=/root/.cache/go-build,sharing=locked \
    build-go-tools "${TARGETARCH}" /out

FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG TARGETARCH
ARG UBUNTU_SNAPSHOT=20260715T000000Z
ARG RUNTIME_UID=1000
ARG RUNTIME_GID=1000

ARG AWS_CLI_VERSION=2.36.2
ARG AWS_CLI_AMD64_SHA256=88045926e48315681b73ec1d4e430ae6917b0eaffc6368d34bcc07bf9fe9fcb9
ARG AWS_CLI_ARM64_SHA256=7f41af8314f5a8d84742a7cf3e37e55d898355a6b605bcacb68adcf563c73064

ARG TFENV_VERSION=3.2.2
ARG TFENV_COMMIT=de6ce2e809c155cbc5e2cfeb3b1bef151244e045
ARG TFENV_SHA256=a0f681f2434e8b27b2de8de05618c1b4d5bb867ea3724337fa39083cd3c77bb0

ARG TGENV_VERSION=1.3.0
ARG TGENV_COMMIT=fc6b4bc42913126ab3c0061896ba0fa920e07a84
ARG TGENV_SHA256=744bec99b007fbb8456a67678886bb0a86e44747acf7376d096f4157c64e9935

COPY requirements.${TARGETARCH}.lock /tmp/requirements.lock
COPY scripts/download-and-verify /usr/local/bin/download-and-verify
COPY --from=tool-builder /out/ /usr/local/bin/

# The verified downloads use a build-local temporary directory that cannot be
# represented by a fixed Docker WORKDIR.
# hadolint ignore=DL3003
RUN \
    set -eux && \
    printf '%s\n' "${UBUNTU_SNAPSHOT}" | grep -Eq '^[0-9]{8}T[0-9]{6}Z$' && \
    snapshot_url="https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}" && \
    rm -f /etc/apt/sources.list.d/* && \
    printf '%s\n' \
        "deb ${snapshot_url} noble main restricted universe multiverse" \
        "deb ${snapshot_url} noble-updates main restricted universe multiverse" \
        "deb ${snapshot_url} noble-security main restricted universe multiverse" \
        > /etc/apt/sources.list && \
    # The minimal base has no CA bundle yet. APT still verifies the snapshot's
    # signed metadata and package hashes during this CA-only bootstrap; normal
    # TLS peer verification is restored before any other package is installed.
    printf '%s\n' 'Acquire::https::Verify-Peer "false";' \
        > /etc/apt/apt.conf.d/99snapshot-bootstrap && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates && \
    rm /etc/apt/apt.conf.d/99snapshot-bootstrap && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        bat \
        curl \
        fd-find \
        git \
        jq \
        libcap2-bin \
        openssh-client \
        python3-venv \
        unzip \
        vim \
        zsh && \
    case "${TARGETARCH}" in \
        amd64) \
            aws_arch=x86_64; \
            aws_sha256="${AWS_CLI_AMD64_SHA256}" \
            ;; \
        arm64) \
            aws_arch=aarch64; \
            aws_sha256="${AWS_CLI_ARM64_SHA256}" \
            ;; \
        *) \
            echo "unsupported TARGETARCH: ${TARGETARCH}" >&2; \
            exit 1 \
            ;; \
    esac && \
    tmp_dir=$(mktemp -d) && \
    cd "${tmp_dir}" && \
    aws_archive="awscli-exe-linux-${aws_arch}-${AWS_CLI_VERSION}.zip" && \
    download-and-verify \
        "https://awscli.amazonaws.com/${aws_archive}" \
        "${aws_archive}" \
        "${aws_sha256}" && \
    unzip -q "${aws_archive}" && \
    ./aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli && \
    download-and-verify \
        "https://codeload.github.com/tfutils/tfenv/tar.gz/${TFENV_COMMIT}" \
        tfenv.tar.gz \
        "${TFENV_SHA256}" && \
    mkdir -p /opt/tfenv && \
    tar -xzf tfenv.tar.gz -C /opt/tfenv --strip-components=1 && \
    ln -s /opt/tfenv/bin/terraform /usr/local/bin/terraform && \
    ln -s /opt/tfenv/bin/tfenv /usr/local/bin/tfenv && \
    download-and-verify \
        "https://codeload.github.com/tgenv/tgenv/tar.gz/${TGENV_COMMIT}" \
        tgenv.tar.gz \
        "${TGENV_SHA256}" && \
    mkdir -p /opt/tgenv && \
    tar -xzf tgenv.tar.gz -C /opt/tgenv --strip-components=1 && \
    ln -s /usr/local/bin/tgenv-wrapper /usr/local/bin/terragrunt && \
    ln -s /usr/local/bin/tgenv-wrapper /usr/local/bin/tgenv && \
    python3 -m venv /opt/python && \
    /opt/python/bin/python -m pip install --no-cache-dir --require-hashes \
        --requirement /tmp/requirements.lock && \
    ln -s /usr/bin/fdfind /usr/local/bin/fd && \
    ln -s /usr/bin/batcat /usr/local/bin/bat && \
    # Ubuntu 24.04 reserves UID/GID 1000 for its unused default account.
    # Remove it before preserving the image's established terraform identity.
    userdel --remove ubuntu && \
    groupadd --gid "${RUNTIME_GID}" terraform && \
    useradd \
        --create-home \
        --gid "${RUNTIME_GID}" \
        --shell /bin/zsh \
        --uid "${RUNTIME_UID}" \
        terraform && \
    install -d \
        -o terraform \
        -g terraform \
        /workspace \
        /home/terraform/.cache/pre-commit \
        /home/terraform/.terraform.d/plugin-cache \
        /home/terraform/.tfenv \
        /home/terraform/.tgenv && \
    printf '%s\n' \
        "alias tf='terraform'" \
        "alias tg='terragrunt'" \
        >> /etc/bash.bashrc && \
    printf '%s\n' \
        "alias tf='terraform'" \
        "alias tg='terragrunt'" \
        >> /etc/zsh/zshrc && \
    cd / && \
    rm -rf \
        "${tmp_dir}" \
        /tmp/requirements.lock \
        /usr/local/bin/download-and-verify \
        /var/lib/apt/lists/* && \
    apt-get clean

COPY --chmod=0755 scripts/tgenv-wrapper /usr/local/bin/tgenv-wrapper

ENV HOME=/home/terraform \
    HISTFILE=/home/terraform/.zsh_history \
    PATH=/opt/python/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    TFENV_CONFIG_DIR=/home/terraform/.tfenv \
    TF_PLUGIN_CACHE_DIR=/home/terraform/.terraform.d/plugin-cache

USER terraform
WORKDIR /workspace
CMD ["/bin/zsh"]
