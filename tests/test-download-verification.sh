#!/bin/sh

set -eu

repo_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
verifier="$repo_root/scripts/download-and-verify"
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

printf 'verified build input\n' > "$tmp_dir/source"
expected_sha256=$(sha256sum "$tmp_dir/source" | awk '{print $1}')

"$verifier" "file://$tmp_dir/source" "$tmp_dir/accepted" "$expected_sha256"
cmp "$tmp_dir/source" "$tmp_dir/accepted"

invalid_sha256=0000000000000000000000000000000000000000000000000000000000000000
if "$verifier" "file://$tmp_dir/source" "$tmp_dir/rejected" "$invalid_sha256"; then
    echo 'download verifier accepted an invalid digest' >&2
    exit 1
fi

if [ -e "$tmp_dir/rejected" ] || [ -e "$tmp_dir/rejected.part" ]; then
    echo 'download verifier retained unverified output' >&2
    exit 1
fi
