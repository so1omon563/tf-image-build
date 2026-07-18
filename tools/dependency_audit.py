#!/usr/bin/env python3
"""Report available updates for pins that Dependabot cannot maintain safely."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "tf-image-build-dependency-audit/1"


@dataclass(frozen=True)
class Check:
    name: str
    current: str
    source: str
    release_url: str


@dataclass(frozen=True)
class Result:
    name: str
    current: str
    latest: str
    release_url: str

    @property
    def update_available(self) -> bool:
        return self.current != self.latest


GITHUB_RELEASES = {
    "Terraform Docs": ("TERRAFORM_DOCS_VERSION", "terraform-docs/terraform-docs"),
    "TFLint": ("TFLINT_VERSION", "terraform-linters/tflint"),
    "Trivy": ("TRIVY_VERSION", "aquasecurity/trivy"),
    "fzf": ("FZF_VERSION", "junegunn/fzf"),
    "tenv": ("TENV_VERSION", "tofuutils/tenv"),
}

PYPI_PROJECTS = {
    "Checkov": "checkov",
    "pre-commit": "pre-commit",
}


def read_docker_args(path: Path) -> dict[str, str]:
    args: dict[str, str] = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"ARG ([A-Z0-9_]+)=(\S+)", line)
        if match:
            args[match.group(1)] = match.group(2)
    return args


def read_requirements(path: Path) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s#]+)", line.strip())
        if match:
            requirements[match.group(1).lower()] = match.group(2)
    return requirements


def read_actionlint_version(path: Path) -> str:
    match = re.search(r"docker://rhysd/actionlint:v?([^\s]+)", path.read_text())
    if not match:
        raise ValueError(f"actionlint docker reference not found in {path}")
    return match.group(1)


def read_hadolint_version(path: Path) -> str:
    match = re.search(r"hadolint/hadolint:v?([^\s]+)", path.read_text())
    if not match:
        raise ValueError(f"hadolint container reference not found in {path}")
    return match.group(1)


def build_checks(root: Path = ROOT) -> list[Check]:
    docker_args = read_docker_args(root / "Dockerfile")
    requirements = read_requirements(root / "requirements.in")
    checks = [
        Check(
            "AWS CLI",
            docker_args["AWS_CLI_VERSION"],
            "github-tag:aws/aws-cli",
            "https://github.com/aws/aws-cli/blob/v2/CHANGELOG.rst",
        ),
        Check(
            "Go",
            docker_args["GO_VERSION"],
            "go-release:go",
            "https://go.dev/dl/",
        ),
    ]

    for name, (arg, repository) in GITHUB_RELEASES.items():
        checks.append(
            Check(
                name,
                docker_args[arg],
                f"github-release:{repository}",
                f"https://github.com/{repository}/releases/latest",
            )
        )

    # tfenv's latest GitHub Release is stale; its maintained versions are tags.
    checks.append(
        Check(
            "tfenv",
            docker_args["TFENV_VERSION"],
            "github-tag:tfutils/tfenv",
            "https://github.com/tfutils/tfenv/tags",
        )
    )

    checks.append(
        Check(
            "actionlint",
            read_actionlint_version(root / ".github/workflows/image_ci.yml"),
            "github-release:rhysd/actionlint",
            "https://github.com/rhysd/actionlint/releases/latest",
        )
    )

    checks.append(
        Check(
            "Hadolint",
            read_hadolint_version(root / ".github/workflows/image_ci.yml"),
            "github-release:hadolint/hadolint",
            "https://github.com/hadolint/hadolint/releases/latest",
        )
    )

    for name, project in PYPI_PROJECTS.items():
        checks.append(
            Check(
                name,
                requirements[project],
                f"pypi:{project}",
                f"https://pypi.org/project/{project}/#history",
            )
        )

    return checks


def fetch_json(url: str) -> dict | list:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def strip_version_prefix(version: str) -> str:
    return version.removeprefix("go").removeprefix("v")


def stable_version_key(version: str) -> tuple[int, ...] | None:
    normalized = strip_version_prefix(version)
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", normalized):
        return None
    return tuple(int(part) for part in normalized.split("."))


def resolve_latest(source: str, fetcher: Callable[[str], dict | list] = fetch_json) -> str:
    kind, value = source.split(":", 1)
    if kind == "github-release":
        data = fetcher(f"https://api.github.com/repos/{value}/releases/latest")
        if not isinstance(data, dict) or not isinstance(data.get("tag_name"), str):
            raise ValueError(f"unexpected latest-release response for {value}")
        return strip_version_prefix(data["tag_name"])
    if kind == "github-tag":
        data = fetcher(f"https://api.github.com/repos/{value}/tags?per_page=100")
        if not isinstance(data, list):
            raise ValueError(f"unexpected tags response for {value}")
        versions = [
            (stable_version_key(item["name"]), strip_version_prefix(item["name"]))
            for item in data
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and stable_version_key(item["name"]) is not None
        ]
        if not versions:
            raise ValueError(f"no stable version tags found for {value}")
        return max(versions)[1]
    if kind == "go-release":
        data = fetcher("https://go.dev/dl/?mode=json")
        if not isinstance(data, list):
            raise ValueError("unexpected Go releases response")
        versions = [
            (stable_version_key(item["version"]), strip_version_prefix(item["version"]))
            for item in data
            if isinstance(item, dict)
            and item.get("stable") is True
            and isinstance(item.get("version"), str)
            and stable_version_key(item["version"]) is not None
        ]
        if not versions:
            raise ValueError("no stable Go releases found")
        return max(versions)[1]
    if kind == "pypi":
        data = fetcher(f"https://pypi.org/pypi/{value}/json")
        if not isinstance(data, dict) or not isinstance(data.get("info", {}).get("version"), str):
            raise ValueError(f"unexpected PyPI response for {value}")
        return data["info"]["version"]
    raise ValueError(f"unsupported dependency source: {kind}")


def audit(
    checks: list[Check],
    fetcher: Callable[[str], dict | list] = fetch_json,
) -> tuple[list[Result], list[str]]:
    results: list[Result] = []
    errors: list[str] = []
    for check in checks:
        try:
            latest = resolve_latest(check.source, fetcher)
            results.append(Result(check.name, check.current, latest, check.release_url))
        except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
            errors.append(f"{check.name}: {error}")
    return results, errors


def snapshot_result(root: Path, now: dt.datetime) -> Result:
    value = read_docker_args(root / "Dockerfile")["UBUNTU_SNAPSHOT"]
    snapshot = dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    age = now.astimezone(dt.timezone.utc) - snapshot
    latest = value if age <= dt.timedelta(days=14) else "refresh required"
    return Result(
        "Ubuntu snapshot",
        value,
        latest,
        "https://snapshot.ubuntu.com/",
    )


def render_report(results: list[Result], errors: list[str], generated: dt.datetime) -> str:
    update_count = sum(result.update_available for result in results)
    lines = [
        "# Manual dependency audit",
        "",
        f"Generated: {generated.astimezone(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Dependency | Current | Latest | Status | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        status = "update available" if result.update_available else "current"
        lines.append(
            f"| {result.name} | `{result.current}` | `{result.latest}` | {status} "
            f"| [upstream]({result.release_url}) |"
        )

    lines.extend(["", f"Updates available: **{update_count}**."])
    if errors:
        lines.extend(["", "## Audit errors", ""])
        lines.extend(f"- {error}" for error in errors)
    if update_count:
        lines.extend(
            [
                "",
                "## Next step",
                "",
                "Prepare reviewed dependency pull requests using `DEPENDENCY_UPDATES.md`. "
                "Keep majors and incompatible changes separate, include current/target and "
                "release-note evidence, and require the full native image test and scan.",
            ]
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the Markdown report to this path")
    parser.add_argument(
        "--github-output",
        type=Path,
        help="append an updates=true/false output for GitHub Actions",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    try:
        checks = build_checks()
        results, errors = audit(checks)
        results.append(snapshot_result(ROOT, now))
    except (KeyError, OSError, ValueError) as error:
        print(f"dependency audit configuration error: {error}", file=sys.stderr)
        return 1

    report = render_report(results, errors, now)
    if args.output:
        args.output.write_text(report)
    else:
        print(report, end="")

    if args.github_output:
        updates = any(result.update_available for result in results)
        with args.github_output.open("a") as output:
            output.write(f"updates={str(updates).lower()}\n")

    if errors:
        print("dependency audit could not check every source", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
