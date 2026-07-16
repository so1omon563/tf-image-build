# How to use the Terraform image

> The files in this directory are example patterns, not a required integration.
> Copy and adapt them to match the authentication and caching needs of each
> Terraform repository.

## Copy and configure the examples

Copy these files to the root of the Terraform repository that will use the
image:

- `.image` selects the image and tag to run.
- `.terraform-version` selects the Terraform version through `tfenv`.
- `.terragrunt-version` selects the Terragrunt version through `tgenv`; omit it
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
IMAGE=so1omon/tf_image:latest
```

`latest` follows the newest published image. Replace it with an immutable
version tag for reproducible local or CI use.

### `.terraform-version`

This plain-text file selects the Terraform version that `tfenv install` will
install:

```text
1.5.0
```

### `.terragrunt-version`

This plain-text file selects the Terragrunt version that `tgenv install` will
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

Terraform and Terragrunt are intentionally not installed during shell startup.
Install the repository-selected versions inside the container when needed:

```shell
tfenv install
tgenv install
terraform version
terragrunt --version
```

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
use it to inject temporary AWS environment variables into either launcher:

```shell
aws-runas -E <profile_name> ./tf_image
aws-runas -E <profile_name> ./tg_ci.sh terraform plan
```

The example launcher forwards populated `AWS_*` variables. It also mounts an
existing host `~/.aws` directory read-write and an existing `~/.ssh` directory
read-only. Those broad mounts are convenient for local development, but should
be reviewed and narrowed before copying the launcher into shared automation.
Prefer short-lived environment credentials and purpose-specific SSH access
where possible.
