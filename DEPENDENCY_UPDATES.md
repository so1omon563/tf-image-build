# Dependency update process

Dependency changes are reviewed pull requests. They are never merged or
published directly by scheduled automation.

## Automated detection

Dependabot checks the Docker base and GitHub Actions weekly. Minor and patch
Action updates may share one pull request; major updates remain separate. The
Docker queue is limited to one open pull request, and both ecosystems use a
seven-day cooldown for routine version updates. Dependabot security updates are
not delayed by that cooldown.

GitHub does not update container references embedded in workflow shell commands,
the `docker://` Action reference, or the version and checksum pairs in the
Dockerfile. The Wednesday dependency audit therefore checks:

- the AWS CLI and every downloaded release pinned in `Dockerfile`;
- the workflow-only `docker://rhysd/actionlint` and Hadolint container
  references;
- the direct Python requirements in `requirements.in`; and
- whether the Ubuntu archive snapshot is more than 14 days old.

The audit writes its evidence to the workflow summary and maintains one rolling
GitHub issue named `Dependency audit: manual pins need review`. It closes that
issue when all monitored pins are current. A failed audit means a source could
not be checked and must be investigated; it must not be treated as a clean
result.

## Preparing an update

The repository CODEOWNER owns routine triage. Security-sensitive updates are
handled first and kept separate from unrelated changes. Major updates and
updates with incompatible release notes also get separate pull requests.

Each dependency pull request must include:

1. the current and target versions;
2. a link to upstream release notes or package history;
3. regenerated AMD64 and ARM64 checksums or Python locks, when applicable;
4. any migration or compatibility notes; and
5. confirmation that the full native AMD64 and ARM64 image CI and security scan
   passed.

For Python updates, change `requirements.in` and regenerate both lock files with
the commands in the README. Binary and source archive updates must refresh every
architecture checksum and retain the existing download verification. A Trivy
update must also refresh the pinned scanner image digest in `scripts/scan-image`
and the version recorded in `SECURITY.md`.

If an update fails, document the failure and the retry or deferral rationale in
the rolling issue or pull request. Security deferrals require a Linear issue and
the time-bounded exception process in `SECURITY.md`.
