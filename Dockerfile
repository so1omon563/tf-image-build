FROM ubuntu:22.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN \
    apt-get update && \
    apt-get install -y --no-install-recommends python3-pip curl git openssh-client vim jq libcap2-bin unzip zsh fd-find bat && \
    curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash && \
    curl -sSLo ./terraform-docs.tar.gz https://terraform-docs.io/dl/v0.16.0/terraform-docs-v0.16.0-$(uname)-amd64.tar.gz && tar -xzf terraform-docs.tar.gz && chmod +x terraform-docs && mv terraform-docs /usr/bin/ && \
    curl -L "$(curl -s https://api.github.com/repos/aquasecurity/tfsec/releases/latest | grep -o -E -m 1 "https://.+?tfsec-linux-amd64")" > tfsec && chmod +x tfsec && mv tfsec /usr/bin/ && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && ./aws/install && rm -rf awscliv2.zip aws && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /workspace && \
    git clone --depth 1 https://github.com/tfutils/tfenv.git ~/.tfenv && \
    echo 'export PATH="$HOME/.tfenv/bin:$PATH"' >> ~/.zprofile && \
    ln -s ~/.tfenv/bin/* /usr/local/bin && \
    git clone --depth 1 https://github.com/tgenv/tgenv.git ~/.tgenv && \
    echo 'export PATH="$HOME/.tgenv/bin:$PATH"' >> ~/.zprofile && \
    ln -s ~/.tgenv/bin/* /usr/local/bin && \
    pip install --no-cache-dir pre-commit && \
    pip install --no-cache-dir -U checkov && \
    git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf && ~/.fzf/install --all && \
    ln -s /usr/bin/fdfind /usr/local/bin/fd && \
    ln -s /usr/bin/batcat /usr/local/bin/bat && \
    ln -s /root/.fzf/bin/fzf /usr/local/bin/fzf && \
    echo "export HISTFILE=~/.zsh_history" >> ~/.zshrc && \
    echo "export HISTFILE=~/.zsh_history" >> ~/.bashrc && \
    echo "alias tf='terraform'" >> ~/.bashrc && \
    echo "alias tg='terragrunt'" >> ~/.bashrc && \
    echo "alias tf='terraform'" >> ~/.zshrc && \
    echo "alias tg='terragrunt'" >> ~/.zshrc && \
    usermod -s /bin/zsh root

WORKDIR /workspace

CMD ["/bin/zsh"]
