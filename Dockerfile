FROM ubuntu:22.04@sha256:0e0a0fc6d18feda9db1590da249ac93e8d5abfea8f4c3c0c849ce512b5ef8982

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG TARGETARCH
ARG UBUNTU_SNAPSHOT=20260715T000000Z

ARG AWS_CLI_VERSION=2.35.23
ARG AWS_CLI_AMD64_SHA256=db818de6dd8096d19ac275341721f96bcd70511377446d11c9149a5ed71f8b43
ARG AWS_CLI_ARM64_SHA256=916b13882246140a4d95f0daafe0793950476d72b49f6706f05a5bf1a7f45952

ARG TERRAFORM_DOCS_VERSION=0.24.0
ARG TERRAFORM_DOCS_AMD64_SHA256=9005daf969de0b50134493a2c00078b49f5f5b39d021cda7c89bf4d4f3d776d3
ARG TERRAFORM_DOCS_ARM64_SHA256=d12bd7b73c1fc9c64efc79f8157dd713dabd559f1ecf3cfc0f42e32279a155fd

ARG TFLINT_VERSION=0.63.1
ARG TFLINT_AMD64_SHA256=8441a7d97df20431f19c9b9d27ff4c63e308c964e86660bc7cc0cf7bbe0725e8
ARG TFLINT_ARM64_SHA256=6d858ca7f11858c3fe3c5e29cc746823abccb55e2d2e2da130fa7ad7ea4eecb8

ARG TRIVY_VERSION=0.70.0
ARG TRIVY_AMD64_SHA256=8b4376d5d6befe5c24d503f10ff136d9e0c49f9127a4279fd110b727929a5aa9
ARG TRIVY_ARM64_SHA256=2f6bb988b553a1bbac6bdd1ce890f5e412439564e17522b88a4541b4f364fc8d

ARG FZF_VERSION=0.74.0
ARG FZF_AMD64_SHA256=cf919f05b7581b4c744d764eaa704665d61dd6d3ca785f0df2351281dff60cda
ARG FZF_ARM64_SHA256=bd9e6165ebdb702215d42368cbb95b8dd70a4e77ee97925adac8c31660e30ef7

ARG TFENV_VERSION=3.2.2
ARG TFENV_COMMIT=de6ce2e809c155cbc5e2cfeb3b1bef151244e045
ARG TFENV_SHA256=a0f681f2434e8b27b2de8de05618c1b4d5bb867ea3724337fa39083cd3c77bb0

ARG TGENV_VERSION=1.3.0
ARG TGENV_COMMIT=fc6b4bc42913126ab3c0061896ba0fa920e07a84
ARG TGENV_SHA256=744bec99b007fbb8456a67678886bb0a86e44747acf7376d096f4157c64e9935

COPY requirements.${TARGETARCH}.lock /tmp/requirements.lock
COPY scripts/download-and-verify /usr/local/bin/download-and-verify

# The verified downloads use a build-local temporary directory that cannot be
# represented by a fixed Docker WORKDIR.
# hadolint ignore=DL3003
RUN \
    set -eux && \
    printf '%s\n' "${UBUNTU_SNAPSHOT}" | grep -Eq '^[0-9]{8}T[0-9]{6}Z$' && \
    snapshot_url="https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}" && \
    printf '%s\n' \
        "deb ${snapshot_url} jammy main restricted universe multiverse" \
        "deb ${snapshot_url} jammy-updates main restricted universe multiverse" \
        "deb ${snapshot_url} jammy-security main restricted universe multiverse" \
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
        python3-pip \
        unzip \
        vim \
        zsh && \
    case "${TARGETARCH}" in \
        amd64) \
            aws_arch=x86_64; \
            aws_sha256="${AWS_CLI_AMD64_SHA256}"; \
            terraform_docs_sha256="${TERRAFORM_DOCS_AMD64_SHA256}"; \
            tflint_sha256="${TFLINT_AMD64_SHA256}"; \
            trivy_arch=64bit; \
            trivy_sha256="${TRIVY_AMD64_SHA256}"; \
            fzf_sha256="${FZF_AMD64_SHA256}" \
            ;; \
        arm64) \
            aws_arch=aarch64; \
            aws_sha256="${AWS_CLI_ARM64_SHA256}"; \
            terraform_docs_sha256="${TERRAFORM_DOCS_ARM64_SHA256}"; \
            tflint_sha256="${TFLINT_ARM64_SHA256}"; \
            trivy_arch=ARM64; \
            trivy_sha256="${TRIVY_ARM64_SHA256}"; \
            fzf_sha256="${FZF_ARM64_SHA256}" \
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
    terraform_docs_archive="terraform-docs-v${TERRAFORM_DOCS_VERSION}-linux-${TARGETARCH}.tar.gz" && \
    download-and-verify \
        "https://github.com/terraform-docs/terraform-docs/releases/download/v${TERRAFORM_DOCS_VERSION}/${terraform_docs_archive}" \
        "${terraform_docs_archive}" \
        "${terraform_docs_sha256}" && \
    tar -xzf "${terraform_docs_archive}" -C /usr/local/bin terraform-docs && \
    tflint_archive="tflint_linux_${TARGETARCH}.zip" && \
    download-and-verify \
        "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/${tflint_archive}" \
        "${tflint_archive}" \
        "${tflint_sha256}" && \
    unzip -q "${tflint_archive}" -d /usr/local/bin && \
    trivy_archive="trivy_${TRIVY_VERSION}_Linux-${trivy_arch}.tar.gz" && \
    download-and-verify \
        "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/${trivy_archive}" \
        "${trivy_archive}" \
        "${trivy_sha256}" && \
    tar -xzf "${trivy_archive}" -C /usr/local/bin trivy && \
    fzf_archive="fzf-${FZF_VERSION}-linux_${TARGETARCH}.tar.gz" && \
    download-and-verify \
        "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/${fzf_archive}" \
        "${fzf_archive}" \
        "${fzf_sha256}" && \
    tar -xzf "${fzf_archive}" -C /usr/local/bin fzf && \
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
    ln -s /opt/tgenv/bin/terragrunt /usr/local/bin/terragrunt && \
    ln -s /opt/tgenv/bin/tgenv /usr/local/bin/tgenv && \
    python3 -m pip install --no-cache-dir --require-hashes \
        --requirement /tmp/requirements.lock && \
    ln -s /usr/bin/fdfind /usr/local/bin/fd && \
    ln -s /usr/bin/batcat /usr/local/bin/bat && \
    mkdir -p /workspace && \
    echo "export HISTFILE=~/.zsh_history" >> /root/.zshrc && \
    echo "export HISTFILE=~/.zsh_history" >> /root/.bashrc && \
    echo "alias tf='terraform'" >> /root/.bashrc && \
    echo "alias tg='terragrunt'" >> /root/.bashrc && \
    echo "alias tf='terraform'" >> /root/.zshrc && \
    echo "alias tg='terragrunt'" >> /root/.zshrc && \
    usermod -s /bin/zsh root && \
    cd / && \
    rm -rf \
        "${tmp_dir}" \
        /tmp/requirements.lock \
        /usr/local/bin/download-and-verify \
        /var/lib/apt/lists/* && \
    apt-get clean

WORKDIR /workspace

CMD ["/bin/zsh"]
