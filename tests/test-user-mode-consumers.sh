#!/bin/sh

set -eu

image=${1:?usage: test-user-mode-consumers.sh IMAGE}
network=tf-image-imds-$$
fixture=tf-image-imds-fixture-$$

cleanup() {
    docker rm -f "$fixture" >/dev/null 2>&1 || true
    docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

docker network create "$network" >/dev/null
docker run --detach --name "$fixture" \
    --network "$network" \
    --network-alias host.docker.internal \
    --entrypoint python3 \
    --volume "$PWD/tests/imds-fixture.py:/fixture.py:ro" \
    "$image" /fixture.py >/dev/null

attempt=0
until docker exec "$fixture" python3 -c \
    'import urllib.request; urllib.request.urlopen("http://127.0.0.1:18080/", timeout=1)'; do
    attempt=$((attempt + 1))
    [ "$attempt" -lt 10 ] || exit 1
done

docker run --rm \
    --network "$network" \
    --env AWS_CONFIG_FILE=/dev/null \
    --env AWS_SHARED_CREDENTIALS_FILE=/dev/null \
    --env AWS_EC2_METADATA_DISABLED=false \
    "$image" sh -ceu '
        test "$AWS_EC2_METADATA_SERVICE_ENDPOINT" = http://host.docker.internal:18080
        tmp=$(mktemp -d)
        trap '\''rm -rf "$tmp"'\'' EXIT HUP INT TERM

        aws configure export-credentials --format process > "$tmp/aws.json"
        jq -e \
            '\''.Version == 1 and .AccessKeyId == "ASIAIOSFODNN7EXAMPLE" and .Expiration != null'\'' \
            "$tmp/aws.json" >/dev/null

        cd "$tmp"
        printf "%s\n" 1.15.8 > .terraform-version
        tfenv install
        cat > main.tf <<'\''EOF'\''
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.56.0"
    }
  }
}

provider "aws" {
  region                      = "us-east-1"
  skip_credentials_validation = true
  skip_region_validation      = true
  skip_requesting_account_id  = true
}

data "aws_partition" "current" {}
EOF
        terraform init -input=false >/dev/null
        terraform plan -input=false -refresh=false -out="$tmp/plan" >/dev/null
    '

requests=$(docker logs "$fixture" 2>&1 | grep -c '^credential-request$')
if [ "$requests" -lt 2 ]; then
    echo "expected AWS CLI and Terraform provider credential requests, got $requests" >&2
    exit 1
fi

printf 'synthetic credential consumers passed (%s requests)\n' "$requests"
