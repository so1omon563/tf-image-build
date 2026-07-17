# Terragrunt / Terraform image

Simple image to handle running Terraform / Terragrunt. It also includes a pinned toolchain for Terraform documentation, linting, security scanning, and pre-commit checks.

Uses GitHub Actions to build. Build output can be found [here](https://hub.docker.com/r/so1omon/tf_image).

## Supported platforms

Published version tags and `latest` are multi-platform images for Linux AMD64 and Linux ARM64. Docker selects the native variant automatically, including on Apple Silicon hosts. Use an explicit `--platform` only when intentionally testing compatibility with the other architecture.

## Runtime contract

The image starts `/bin/zsh` as the unprivileged `terraform` user. The example launcher further maps the container process to the host UID/GID so files written into the workspace retain host ownership on Linux and macOS. Its writable home and tool caches live under the host's `~/.cache/tf-image`; host AWS configuration, AWS environment credentials, SSH keys, and SSH agents are not exposed by default.

Credential access is explicit. The launcher can forward populated AWS environment variables, mount `~/.aws` read-only, or forward only `SSH_AUTH_SOCK`; it never mounts the host's private-key directory. See [`example_usage`](example_usage/README.md) for the opt-in variables and trust boundary.

Common Ubuntu package names are exposed as the expected `fd` and `bat` commands, and retained tools are available to non-interactive commands through the image `PATH`.

Terraform and Terragrunt versions are not baked into the image or installed during shell startup. Add `.terraform-version` and `.terragrunt-version` files to a workspace, then run `tfenv install` and `tgenv install` explicitly.

Copy-ready examples for interactive development and non-interactive automation are documented in [`example_usage`](example_usage/README.md).

## Bundled toolchain

| Tool | Version | Purpose |
| --- | --- | --- |
| AWS CLI | 2.35.23 | AWS API access |
| terraform-docs | 0.24.0 | Terraform documentation generation |
| TFLint | 0.63.1 | Terraform linting and provider rules |
| Trivy | 0.72.0 | IaC misconfiguration scanning and broader repository scanning |
| Checkov | 3.3.8 | Compatibility with existing Checkov policies and pre-commit hooks |
| pre-commit | 4.6.0 | Repository hook execution |
| tfenv | 3.2.2 | Workspace-selected Terraform versions |
| tgenv | 1.3.0 (`fc6b4bc`) | Workspace-selected Terragrunt versions |
| fzf | 0.74.0 | Interactive command-line selection |

Release binaries are selected from BuildKit's target architecture and checked against pinned SHA-256 digests. The architecture-independent `tfenv` and `tgenv` source archives are pinned to exact commits and digests. The Ubuntu 24.04 LTS base is pinned to a multi-platform OCI digest, and APT resolves Noble packages from one dated Canonical archive snapshot. Checkov, pre-commit, and every Python transitive dependency are installed into an isolated Python 3.12 virtual environment from the matching `requirements.amd64.lock` or `requirements.arm64.lock` with required SHA-256 hashes. `aws-runas` is intentionally host-side and is not bundled.

The direct Python requirements live in `requirements.in`. Regenerate each lock on its target architecture under Python 3.12 with pip-tools 7.5.2. This matters because dependency markers can produce architecture-specific graphs:

```console
docker run --rm --platform linux/amd64 -v "$PWD:/src" -w /src python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de sh -c 'pip install pip-tools==7.5.2 && pip-compile --strip-extras --generate-hashes --resolver=backtracking --output-file=requirements.amd64.lock requirements.in'
docker run --rm --platform linux/arm64 -v "$PWD:/src" -w /src python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de sh -c 'pip install pip-tools==7.5.2 && pip-compile --strip-extras --generate-hashes --resolver=backtracking --output-file=requirements.arm64.lock requirements.in'
```

The maintained `tgenv` `v1.3.0` tag still prints `tgenv 0.2.0` because its version command reads the first entry in an upstream changelog that was not updated for the tag. The image pins and verifies the `v1.3.0` commit rather than modifying upstream source to disguise that reporting bug.

## Migrating from tfsec to Trivy

The retired `tfsec` binary has been replaced by its maintained successor, Trivy. Update direct invocations as follows:

| tfsec | Trivy |
| --- | --- |
| `tfsec <dir>` | `trivy config --exit-code 1 <dir>` |
| `tfsec <dir> --tf-vars-file <vars.tf>` | `trivy config --exit-code 1 --tf-vars <vars.tf> <dir>` |
| `tfsec <dir> --format json` | `trivy config --exit-code 1 --format json <dir>` |

Unlike `tfsec`, Trivy exits with code 0 on findings by default. Keep `--exit-code 1` in CI migrations so detected misconfigurations continue to fail the job. Trivy refreshes its misconfiguration checks from its registry when available and falls back to embedded checks offline. Rule IDs, defaults, configuration, ignore behavior, and supported report formats can differ from `tfsec`, so existing CI suppressions and expected findings should be reviewed during migration. Checkov remains because existing repositories may depend on its separate policy IDs, custom policies, and pre-commit hooks; it is not a `tfsec` compatibility shim.

## Build and release

Pull requests and updates to `main` run static checks, then build, exercise, and vulnerability-scan the complete runtime contract on native Linux AMD64 and Linux ARM64 GitHub-hosted runners. A weekly scheduled run performs clean builds with a fresh base pull but never tags or publishes an image. Every merged pull request receives an immutable patch tag. GitHub and Docker Hub publication is requested when `#release`, `#publish`, or `#ship` appears in either the pull request title or the merge commit message, so squash, rebase, and merge-commit strategies behave consistently. A marker only in the pull request body does not trigger publication. For a release, each native runner builds its architecture once, pushes it by content digest with SPDX SBOM and max-level provenance attestations, then tests and scans that exact digest after Docker Hub credentials have been removed. The trusted publisher performs no rebuild: it combines only the two validated digests under the immutable version tag and moving `latest` alias, then verifies both tags, platforms, and attestations before creating the GitHub release. See [`SECURITY.md`](SECURITY.md) for the base lifecycle, scan policy, exception rules, and retained evidence.

Dependabot checks the Docker base and GitHub Actions weekly. A separate audit
checks release binaries, source archives, direct Python requirements, the
workflow-only actionlint and Hadolint container references, and Ubuntu snapshot
freshness. See
[`DEPENDENCY_UPDATES.md`](DEPENDENCY_UPDATES.md) for triage, grouping, evidence,
and failed-update requirements.
