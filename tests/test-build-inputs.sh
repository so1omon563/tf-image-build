#!/bin/sh

set -eu

repo_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)

grep -Eq '^FROM ubuntu:22\.04@sha256:[0-9a-f]{64}$' "$repo_root/Dockerfile"
grep -Eq '^ARG UBUNTU_SNAPSHOT=[0-9]{8}T[0-9]{6}Z$' "$repo_root/Dockerfile"
grep -F 'COPY requirements.${TARGETARCH}.lock /tmp/requirements.lock' "$repo_root/Dockerfile" >/dev/null
grep -F -- '--require-hashes' "$repo_root/Dockerfile" >/dev/null
for arch in amd64 arm64; do
    lock="$repo_root/requirements.${arch}.lock"
    grep -Eq '^checkov==3\.3\.8([[:space:]]|$)' "$lock"
    grep -Eq '^pre-commit==4\.6\.0([[:space:]]|$)' "$lock"
done

# Checkov declares Pyston only for CPython on x86_64. Keep each supported
# architecture's fully resolved dependency graph separate.
grep -Eq '^pyston==2\.3\.5([[:space:]]|$)' "$repo_root/requirements.amd64.lock"
grep -Eq '^pyston-autoload==2\.3\.5([[:space:]]|$)' "$repo_root/requirements.amd64.lock"
if grep -Eq '^pyston(-autoload)?==' "$repo_root/requirements.arm64.lock"; then
    echo 'ARM64 lock unexpectedly contains x86-only Pyston packages' >&2
    exit 1
fi

first_context_rule=$(grep -Ev '^[[:space:]]*(#|$)' "$repo_root/.dockerignore" | sed -n '1p')
if [ "$first_context_rule" != '*' ]; then
    echo '.dockerignore must exclude the context by default' >&2
    exit 1
fi
