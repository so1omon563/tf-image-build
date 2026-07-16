#!/bin/sh

set -eu

image=${1:?usage: test-image.sh IMAGE ARCH}
arch=${2:?usage: test-image.sh IMAGE ARCH}

image_cmd=$(docker image inspect --format '{{json .Config.Cmd}}' "$image")
if [ "$image_cmd" != '["/bin/zsh"]' ]; then
    echo "unexpected image command: $image_cmd" >&2
    exit 1
fi

docker run --rm \
    --platform "linux/$arch" \
    --env "EXPECTED_ARCH=$arch" \
    --volume "$PWD/tests:/tests:ro" \
    "$image" \
    /tests/smoke-tool-inventory.sh
