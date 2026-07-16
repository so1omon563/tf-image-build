# Terragrunt / Terraform image

Simple image to handle running Terraform / Terragrunt. It also includes a pinned toolchain for Terraform documentation, linting, security scanning, and pre-commit checks.

Uses GitHub Actions to build. Build output can be found [here](https://hub.docker.com/r/so1omon/tf_image).

## Runtime contract

The image currently starts `/bin/zsh` as `root`. Common Ubuntu package names are exposed as the expected `fd` and `bat` commands, and retained tools are available to non-interactive commands through the image `PATH`.

Terraform and Terragrunt versions are not baked into the image or installed during shell startup. Add `.terraform-version` and `.terragrunt-version` files to a workspace, then run `tfenv install` and `tgenv install` explicitly.

## Bundled toolchain

| Tool | Version | Purpose |
| --- | --- | --- |
| AWS CLI | 2.35.23 | AWS API access |
| terraform-docs | 0.24.0 | Terraform documentation generation |
| TFLint | 0.63.1 | Terraform linting and provider rules |
| Trivy | 0.70.0 | IaC misconfiguration scanning and broader repository scanning |
| Checkov | 3.3.8 | Compatibility with existing Checkov policies and pre-commit hooks |
| pre-commit | 4.6.0 | Repository hook execution |
| tfenv | 3.2.2 | Workspace-selected Terraform versions |
| tgenv | 1.3.0 (`fc6b4bc`) | Workspace-selected Terragrunt versions |
| fzf | 0.74.0 | Interactive command-line selection |

Release binaries are selected from BuildKit's target architecture and checked against pinned SHA-256 digests. The architecture-independent `tfenv` and `tgenv` source archives are pinned to exact commits and digests. Python tools are pinned to exact PyPI versions. `aws-runas` is intentionally host-side and is not bundled.

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

Pull requests and updates to `main` run static checks, build the Linux/AMD64 image, and exercise its runtime contract. A release candidate must pass the same image tests before GitHub and Docker Hub publication. The image build now selects native AMD64 or ARM64 tool artifacts; multi-architecture CI and publication are tracked separately, and the current published image remains Linux/AMD64.
