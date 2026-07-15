#!/bin/sh

set -eu

for command_name in \
    aws \
    checkov \
    pre-commit \
    terraform-docs \
    tfenv \
    tfsec \
    tflint \
    tgenv
do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "missing expected command: $command_name" >&2
        exit 1
    fi
done

if command -v aws-runas >/dev/null 2>&1; then
    echo "aws-runas must not be installed in the image" >&2
    exit 1
fi
