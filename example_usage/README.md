# How to use the Terraform image

> The files in this directory are example patterns, not a required integration.
> Copy and adapt them to match the authentication and caching needs of each
> Terraform repository.

## Copy and configure the examples

Copy these files to the root of the Terraform repository that will use the
image:

- `.image` selects the image and tag to run.
- `.terraform-version` selects the Terraform version through `tfenv`.
- `.terragrunt-version` selects the Terragrunt version through `tenv`; omit it
  when the repository does not use Terragrunt.
- `tf_image` starts an interactive shell or runs one command in the image.
- `tg_ci.sh` runs a command non-interactively after installing the versions
  selected by the repository.

Make the launchers executable after copying them:

```shell
chmod +x tf_image tg_ci.sh
```

Update the two version files for the repository. The versions in this example
directory are illustrative, not image defaults.

## File reference

### `.image`

This shell-sourceable file sets the image used by both launchers:

```shell
IMAGE=so1omon/tf_image:v0.5.0
```

The example pins the non-root image release for reproducible local and CI use.
Change the tag deliberately when adopting a new release. The moving
`latest` channel remains available as an explicit opt-in when reproducibility is
not required.

### `.terraform-version`

This plain-text file selects the Terraform version that `tfenv install` will
install:

```text
1.5.0
```

### `.terragrunt-version`

This plain-text file selects the Terragrunt version that `tenv tg install` will
install:

```text
0.54.19
```

## Interactive local use

From the root of the consuming repository, start a shell with the repository
mounted at `/workspace`:

```shell
./tf_image
```

The launcher maps the container process to the host UID/GID. Workspace files
therefore remain owned by the invoking user instead of root. Writable container
home state, Terraform providers, installed Terraform/Terragrunt versions,
pre-commit data, and shell history are isolated under
`~/.cache/tf-image/home`. Remove that directory to reset the cached runtime
state.

Terraform and Terragrunt are intentionally not installed during shell startup.
Install the repository-selected versions inside the container when needed:

```shell
tfenv install
tenv tg install
terraform version
terragrunt --version
```

Older repositories may continue using `tgenv install`. The image retains a
compatibility facade for the common tgenv commands and `TGENV_*` inputs, but
new integrations should use `tenv tg`. Existing cached home mounts remain
valid; the first run redownloads selected Terragrunt versions into tenv's
checksum-verified internal layout.

The published image supports Linux AMD64 and Linux ARM64. Docker selects the
native variant automatically, including on Apple Silicon; no machine-wide
`DOCKER_DEFAULT_PLATFORM` override is required.

## Non-interactive and CI use

Use `tg_ci.sh` for CI, automation, and one-off commands. It installs versions
from the version files in the same container before running the requested
command:

```shell
# Check Terraform formatting
./tg_ci.sh terraform fmt -check -recursive

# Validate all Terragrunt configurations using the example version
./tg_ci.sh terragrunt run-all validate --terragrunt-non-interactive

# Run repository hooks
./tg_ci.sh pre-commit run --all-files

# Fail when Trivy finds an IaC misconfiguration
./tg_ci.sh trivy config --exit-code 1 .
```

Run `./tg_ci.sh` without arguments to display its command reference.

## AWS and SSH authentication

`aws-runas` is not installed in the image. When it is available on the host,
use it outside the image and explicitly allow the temporary AWS environment to
cross the container boundary:

```shell
aws-runas -E <profile_name> env TF_IMAGE_AWS_ENV=1 ./tf_image
aws-runas -E <profile_name> env TF_IMAGE_AWS_ENV=1 ./tg_ci.sh terraform plan
```

No AWS or SSH material is exposed by default, even when it exists on the host.
Enable only the access required for a run:

| Opt-in | Effect |
| --- | --- |
| `TF_IMAGE_AWS_ENV=1` | Forward only the populated supported `AWS_*` variables. |
| `TF_IMAGE_AWS_CONFIG=1` | Mount host `~/.aws` at the container home read-only. |
| `TF_IMAGE_SSH_AGENT=1` | Forward only the socket named by a valid `SSH_AUTH_SOCK`. |

For example:

```shell
# Use shared AWS config without making it writable in the container.
TF_IMAGE_AWS_CONFIG=1 ./tf_image aws --profile <profile_name> sts get-caller-identity

# Forward an existing SSH agent without exposing ~/.ssh or private key files.
TF_IMAGE_SSH_AGENT=1 ./tf_image git ls-remote git@github.com:owner/private-module.git
```

Each opt-in accepts only `0`, `1`, or an unset value. A requested config
directory or agent socket must exist, otherwise the launcher fails before
calling Docker. Prefer short-lived AWS environment credentials and an SSH agent
over long-lived configuration or private-key mounts.
