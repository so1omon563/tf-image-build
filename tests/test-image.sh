#!/bin/sh

set -eu

image=${1:?usage: test-image.sh IMAGE ARCH}
arch=${2:?usage: test-image.sh IMAGE ARCH}

image_cmd=$(docker image inspect --format '{{json .Config.Cmd}}' "$image")
if [ "$image_cmd" != '["/bin/zsh"]' ]; then
    echo "unexpected image command: $image_cmd" >&2
    exit 1
fi

image_user=$(docker image inspect --format '{{.Config.User}}' "$image")
if [ "$image_user" != terraform ]; then
    echo "unexpected image user: $image_user" >&2
    exit 1
fi

image_size=$(docker image inspect --format '{{.Size}}' "$image")
printf 'image-size-bytes=%s\n' "$image_size"

docker run --rm \
    --platform "linux/$arch" \
    --env "EXPECTED_ARCH=$arch" \
    --volume "$PWD/tests:/tests:ro" \
    "$image" \
    /tests/smoke-tool-inventory.sh

docker run --rm --platform "linux/$arch" "$image" sh -ceu '
    test "$(. /etc/os-release && printf %s "$VERSION_ID")" = 24.04
    ! getent passwd ubuntu
    ! getent group ubuntu
    test ! -e /tmp/requirements.lock
    test ! -e /usr/local/bin/download-and-verify
    test -z "$(find /etc/apt/sources.list.d -mindepth 1 -print -quit)"
    ! grep -Ev "^[[:space:]]*(#|$|deb https://snapshot.ubuntu.com/ubuntu/)" /etc/apt/sources.list
    test -z "$(find /var/lib/apt/lists -maxdepth 1 -type f ! -name lock -print -quit)"
'

launcher_root=$(mktemp -d)
trap 'rm -rf "$launcher_root"' EXIT HUP INT TERM
launcher_workspace="$launcher_root/workspace"
launcher_home="$launcher_root/home"
docker_host=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
mkdir -p "$launcher_workspace" "$launcher_home/.aws"
cp example_usage/tf_image "$launcher_workspace/tf_image"
printf 'IMAGE=%s\n' "$image" > "$launcher_workspace/.image"
printf '[default]\nregion=us-west-2\n' > "$launcher_home/.aws/config"

(
    cd "$launcher_workspace"
    HOME="$launcher_home" DOCKER_HOST="$docker_host" ./tf_image sh -ceu '
        test "$(id -u)" = "$1"
        test -z "${AWS_ACCESS_KEY_ID:-}"
        printf owned > created-by-container
    ' sh "$(id -u)"
)

if owner_uid=$(stat -c %u "$launcher_workspace/created-by-container" 2>/dev/null); then
    :
else
    owner_uid=$(stat -f %u "$launcher_workspace/created-by-container")
fi
if [ "$owner_uid" != "$(id -u)" ]; then
    echo "workspace file owner $owner_uid does not match host user $(id -u)" >&2
    exit 1
fi

(
    cd "$launcher_workspace"
    HOME="$launcher_home" \
    DOCKER_HOST="$docker_host" \
    TF_IMAGE_AWS_CONFIG=1 \
    ./tf_image sh -ceu 'test -r "$HOME/.aws/config" && test ! -w "$HOME/.aws/config"'
)

(
    cd "$launcher_workspace"
    HOME="$launcher_home" \
    DOCKER_HOST="$docker_host" \
    TF_IMAGE_AWS_ENV=1 \
    AWS_ACCESS_KEY_ID=launcher-contract \
    ./tf_image sh -ceu 'test "$AWS_ACCESS_KEY_ID" = launcher-contract'
)

eval "$(ssh-agent -s)" >/dev/null
trap 'ssh-agent -k >/dev/null 2>&1 || true; rm -rf "$launcher_root"' EXIT HUP INT TERM
(
    cd "$launcher_workspace"
    HOME="$launcher_home" \
    DOCKER_HOST="$docker_host" \
    TF_IMAGE_SSH_AGENT=1 \
    ./tf_image sh -ceu '
        test -S "$SSH_AUTH_SOCK"
        status=0
        output=$(ssh-add -l 2>&1) || status=$?
        test "$status" -eq 1
        printf "%s\n" "$output" | grep -F "The agent has no identities."
    '
)
