# How to use the Terraform image

The built image can be used in your Terraform repository by including the following files at the root of your repository:

- `.terraform-version`
A file that specifies the version of Terraform you wish to use. See [tfenv](https://github.com/tfutils/tfenv#terraform-version-file) for details on usage requirements.

- `.terragrunt-version`
A file that specifies the version of Terragrunt you wish to use. See [tgenv](https://github.com/tgenv/tgenv#the-terragrunt-version-file-page_facing_up) for details on usage requirements. If you are not using Terragrunt, this file is not required.

- `.image`
A file that specifies the version of the docker image yo wish to run. The example here uses `latest`.

- `tf_image`
An executable script to use the image.
This will start the container and mount the project directory into the container. It also will mount your local user's .aws and and .ssh directories into the container. This allows for you to use your own AWS credentials and SSH keys.

## Usage
To use, simply execute the `tf_image` script from the root of your repository. You will then be in a shell running on the container, with the repository mounted as /workspace.

```
./tf_image
```

## AWS Authentication
`aws-runas` is not installed in the image. If you have it installed on the host,
you can use it to pass temporary AWS credentials into the container at runtime:

    aws-runas -E <profile_name> ./tf_image

This will set the appropriate `AWS_*` environment variables in the container.

Another useful option is to use the [EC2 metatdata server](https://mmmorris1975.github.io/aws-runas/metadata_credentials.html) built in to `aws-runas`.

An example of some aliases that can be used to start the EC2 metadata server can be found [here](https://gist.github.com/so1omon563/4318631a1a903b3839f353df776f7d13). The example is specifically for putting in `.zshrc`. You may need to modify it if you are using a different shell.
