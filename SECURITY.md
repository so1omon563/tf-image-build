# Image lifecycle and security policy

## Supported base

The image uses Ubuntu 24.04 LTS (Noble), pinned by its multi-platform OCI digest. Canonical provides standard security maintenance for Ubuntu 24.04 LTS through May 2029. Ubuntu 26.04 LTS will be evaluated after its first point release; adoption requires successful native AMD64 and ARM64 image contracts and a reviewed pull request.

The base digest and dated Ubuntu snapshot are reviewed at least quarterly and whenever the weekly lifecycle build reports a fixable critical vulnerability. Base, snapshot, or tool changes are merged through reviewed pull requests. Only a merged pull request carrying an explicit release marker can move the Docker Hub `latest` alias; scheduled jobs never tag or publish images.

## Build and scan cadence

Pull requests, `main`, and the weekly scheduled workflow pull the pinned base before building. The scheduled workflow disables BuildKit cache so stale layers cannot hide package or scanner changes. Release candidates also use a clean, pull-enabled build on native AMD64 and ARM64 runners.

Every built image is exported to a tar archive and scanned without exposing the Docker daemon socket to the scanner. Trivy 0.72.0 is pinned by the multi-platform container digest `sha256:cffe3f5161a47a6823fbd23d985795b3ed72a4c806da4c4df16266c02accdd6f`. Its vulnerability database remains current by design.

The bundled terraform-docs, TFLint, Trivy, and fzf binaries are reproducibly built from verified release commits in a pinned Go 1.26.5 builder. Minimum module overrides are checksum-pinned when an upstream release still embeds a dependency with a fixed HIGH vulnerability. The retained scanner reports remain the authority for the resulting binary contents; version output alone is not treated as remediation evidence.

Trivy scans both OS and application packages and retains a JSON report containing HIGH and CRITICAL findings. A release is blocked when a CRITICAL vulnerability has an available fixed version. Unfixed findings and HIGH findings remain visible in the report so maintainers can update the base or bundled tools without claiming they do not exist.

The currently known unfixed HIGH findings are `CVE-2024-23342` in Python `ecdsa` and `CVE-2026-50163` in `oras-go`. Neither has an upstream fixed version. They stay visible in every report and do not weaken the fixed-CRITICAL gate.

## Exceptions

Exceptions live in `security/trivyignore.yaml` and are empty by default. Any exception must:

- target the narrowest affected path, package URL, or package;
- state why the finding is not currently remediable or exploitable;
- expire within 30 days; and
- link to a Linear issue that owns removal.

Expired or undocumented exceptions must not be renewed silently. A fixed CRITICAL finding may only pass the gate through a reviewed, time-bounded exception.

## Release evidence

Each release-candidate architecture retains its Trivy JSON report for 90 days. Ordinary CI reports are retained for 30 days. The image contract prints the uncompressed image size and verifies that APT metadata, build downloads, and temporary requirements are absent from the final image.

Published images include an SPDX SBOM attestation and max-level build provenance. Immutable version tags are never moved; `latest` points to the most recently reviewed release.
