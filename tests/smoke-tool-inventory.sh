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

for command_name in \
    aws bat checkov curl fd fzf git jq pip3 pre-commit python3 \
    terraform-docs tfenv tfsec tflint tgenv vim zsh
do
    assert_command "$command_name"
done

if command -v aws-runas >/dev/null 2>&1; then
    echo "aws-runas must not be present in the image" >&2
    exit 1
fi

[ "$(id -un)" = root ]
[ "$(getent passwd root | cut -d: -f7)" = /bin/zsh ]
[ "$(uname -m)" = "$expected_uname" ]

aws --version
bat --version
checkov --version
curl --version
fd --version
fzf --version
git --version
jq --version
pip3 --version
pre-commit --version
python3 --version
terraform_docs_version=$(terraform-docs --version)
printf '%s\n' "$terraform_docs_version"
printf '%s\n' "$terraform_docs_version" | grep -F "$expected_docs_arch" >/dev/null
tfenv --version
tfsec --version
tflint --version
tgenv --version
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

if grep -E '^[[:space:]]*terraform([[:space:]]|$)' /root/.bashrc /root/.zshrc; then
    echo "shell startup must not invoke Terraform" >&2
    exit 1
fi

bash -ic 'alias tf >/dev/null; alias tg >/dev/null' 2>/dev/null
zsh -ic 'alias tf >/dev/null; alias tg >/dev/null' 2>/dev/null
