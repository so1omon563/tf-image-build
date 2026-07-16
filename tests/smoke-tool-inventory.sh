#!/bin/sh

set -eu

expected_arch=${EXPECTED_ARCH:?EXPECTED_ARCH must be amd64 or arm64}

case "$expected_arch" in
    amd64)
        expected_uname=x86_64
        expected_docs_arch=linux/amd64
        ;;
    arm64)
        expected_uname=aarch64
        expected_docs_arch=linux/arm64
        ;;
    *)
        echo "unsupported EXPECTED_ARCH: $expected_arch" >&2
        exit 1
        ;;
esac

assert_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "required command is missing: $1" >&2
        exit 1
    fi
}

assert_version() {
    expected=$1
    shift
    version_output=$("$@" 2>&1)
    printf '%s\n' "$version_output"
    if ! printf '%s\n' "$version_output" | grep -F "$expected" >/dev/null; then
        echo "unexpected version from $*: expected output containing $expected" >&2
        exit 1
    fi
}

for command_name in \
    aws bat checkov curl fd fzf git jq pip3 pre-commit python3 ssh \
    terraform-docs tfenv tflint tgenv trivy vim zsh
do
    assert_command "$command_name"
done

if command -v aws-runas >/dev/null 2>&1; then
    echo "aws-runas must not be present in the image" >&2
    exit 1
fi

if command -v tfsec >/dev/null 2>&1; then
    echo "tfsec has been replaced by trivy and must not be present in the image" >&2
    exit 1
fi

[ "$(id -un)" = terraform ]
[ "$(id -u)" = 1000 ]
[ "$(getent passwd terraform | cut -d: -f7)" = /bin/zsh ]
[ "$HOME" = /home/terraform ]
[ "$(uname -m)" = "$expected_uname" ]

touch /workspace/non-root-contract
[ "$(stat -c %u /workspace/non-root-contract)" = "$(id -u)" ]
rm /workspace/non-root-contract

assert_version "aws-cli/2.35.23" aws --version
bat --version
assert_version "3.3.8" checkov --version
curl --version
fd --version
assert_version "0.74.0" fzf --version
git --version
jq --version
pip3 --version
assert_version "pre-commit 4.6.0" pre-commit --version
python3 --version
ssh -V
terraform_docs_version=$(terraform-docs --version 2>&1)
printf '%s\n' "$terraform_docs_version"
printf '%s\n' "$terraform_docs_version" | grep -F "v0.24.0" >/dev/null
printf '%s\n' "$terraform_docs_version" | grep -F "$expected_docs_arch" >/dev/null
assert_version "tfenv 3.2.2" tfenv --version
assert_version "TFLint version 0.63.1" tflint --version
tgenv --version
assert_version "Version: 0.70.0" trivy --version
vim --version >/dev/null
zsh --version

fixture_dir=/tests/fixtures/version-files
version_workspace=$(mktemp -d)
cp "$fixture_dir/.terraform-version" "$fixture_dir/.terragrunt-version" "$version_workspace/"

[ "$(cd "$version_workspace" && tfenv version-name)" = "$(cat "$fixture_dir/.terraform-version")" ]
[ "$(cd "$version_workspace" && tgenv version-name)" = "$(cat "$fixture_dir/.terragrunt-version")" ]

if ! (cd "$version_workspace" && tfenv install) >/tmp/tfenv-install.log 2>&1; then
    cat /tmp/tfenv-install.log >&2
    exit 1
fi
if ! (cd "$version_workspace" && tgenv install) >/tmp/tgenv-install.log 2>&1; then
    cat /tmp/tgenv-install.log >&2
    exit 1
fi
[ "$(cd "$version_workspace" && terraform version -json | jq -r .terraform_version)" = "$(cat "$fixture_dir/.terraform-version")" ]
terragrunt_version=$(cd "$version_workspace" && terragrunt --version)
printf '%s\n' "$terragrunt_version" | grep -F "$(cat "$fixture_dir/.terragrunt-version")" >/dev/null

if grep -E '^[[:space:]]*terraform([[:space:]]|$)' /etc/bash.bashrc /etc/zsh/zshrc; then
    echo "shell startup must not invoke Terraform" >&2
    exit 1
fi

bash -ic 'alias tf >/dev/null; alias tg >/dev/null' 2>/dev/null
zsh -ic 'alias tf >/dev/null; alias tg >/dev/null' 2>/dev/null
