# Terragrunt / Terraform image

Simple image to handle running Terraform / Terragrunt. Also useful for Terraform pre-commit checks including `tfsec`, `tflint`, and `checkov`.

Uses GitHub Actions to build. Build output can be found [here](https://hub.docker.com/r/so1omon/tf_image).

## Runtime contract

The image currently starts `/bin/zsh` as `root`. Common Ubuntu package names are exposed as the expected `fd` and `bat` commands, and retained tools are available to non-interactive commands through the image `PATH`.

Terraform and Terragrunt versions are not baked into the image or installed during shell startup. Add `.terraform-version` and `.terragrunt-version` files to a workspace, then run `tfenv install` and `tgenv install` explicitly.

## Build and release

Pull requests and updates to `main` run static checks, build the Linux/AMD64 image, and exercise its runtime contract. A release candidate must pass the same image tests before GitHub and Docker Hub publication. Multi-architecture publication is tracked separately; the current published image remains Linux/AMD64.
