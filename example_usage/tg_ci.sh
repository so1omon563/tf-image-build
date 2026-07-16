#!/bin/sh

set -eu

if [ "$#" -eq 0 ]; then
    cat >&2 <<'EOF'
Usage: ./tg_ci.sh <command> [args...]

Run a command non-interactively in the Terraform image. If the corresponding
version files exist, Terraform and Terragrunt are installed before the command.

Examples:
  ./tg_ci.sh terraform fmt -check -recursive
  ./tg_ci.sh terragrunt run-all validate --terragrunt-non-interactive
  ./tg_ci.sh pre-commit run --all-files
EOF
    exit 64
fi

if [ ! -x ./tf_image ]; then
    echo "tg_ci.sh: ./tf_image is missing or not executable" >&2
    exit 1
fi

exec ./tf_image sh -ceu '
if [ -f .terraform-version ]; then
    tfenv install
fi
if [ -f .terragrunt-version ]; then
    tgenv install
fi
exec "$@"
' sh "$@"
