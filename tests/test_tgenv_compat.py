import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "tgenv-wrapper"


class TgenvCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.home = self.directory / "home"
        self.bin = self.directory / "bin"
        self.capture = self.directory / "capture"
        self.home.mkdir()
        self.bin.mkdir()

        wrapper = self.bin / "terragrunt-manager"
        shutil.copyfile(WRAPPER, wrapper)
        wrapper.chmod(0o755)
        for command in ("tenv", "tgenv", "terragrunt"):
            (self.bin / command).symlink_to(wrapper)

        self.fake_tenv = self.directory / "fake-tenv"
        self.fake_tenv.write_text(
            textwrap.dedent(
                """\
                #!/bin/sh
                set -eu
                {
                    printf 'root=%s\\n' "${TENV_ROOT:-}"
                    printf 'auto=%s\\n' "${TENV_AUTO_INSTALL:-}"
                    printf 'arch=%s\\n' "${TENV_ARCH:-}"
                    printf 'log=%s\\n' "${TENV_LOG:-}"
                    printf 'no_color=%s\\n' "${NO_COLOR:-}"
                    printf 'token=%s\\n' "${TENV_GITHUB_TOKEN:-}"
                    printf 'args='
                    printf '%s ' "$@"
                    printf '\\n'
                } > "$CAPTURE"

                if [ -n "${FAIL_TENV:-}" ]; then
                    exit "$FAIL_TENV"
                fi
                if [ "${1:-}" = version ]; then
                    echo 'tenv version v4.14.8'
                    exit 0
                fi
                if [ "${1:-}" = tg ] && [ "${2:-}" = list-remote ]; then
                    printf '%s\\n' 1.10.0 1.9.0 0.54.19
                    exit 0
                fi
                if [ "${1:-}" = tg ] && [ "${2:-}" = install ]; then
                    version=$3
                    mkdir -p "$TENV_ROOT/Terragrunt/$version"
                    printf '#!/bin/sh\\n' > "$TENV_ROOT/Terragrunt/$version/terragrunt"
                    chmod +x "$TENV_ROOT/Terragrunt/$version/terragrunt"
                    exit 0
                fi
                if [ "${1:-}" = tg ] && [ "${2:-}" = uninstall ]; then
                    rm -rf "$TENV_ROOT/Terragrunt/$3"
                    exit 0
                fi
                if [ "${1:-}" = tg ] && [ "${2:-}" = use ]; then
                    working_dir=false
                    requested=
                    shift 2
                    for argument in "$@"; do
                        case "$argument" in
                            --no-install) ;;
                            --working-dir) working_dir=true ;;
                            *) requested=$argument ;;
                        esac
                    done
                    if [ "$requested" = latest ]; then
                        requested=$(find "$TENV_ROOT/Terragrunt" -mindepth 1 -maxdepth 1 -type d -exec basename {} \\; | sort -r | sed -n '1p')
                    fi
                    if [ "$working_dir" = true ]; then
                        printf '%s\\n' "$requested" > .terragrunt-version
                    else
                        mkdir -p "$TENV_ROOT/Terragrunt"
                        printf '%s\\n' "$requested" > "$TENV_ROOT/Terragrunt/version"
                    fi
                    exit 0
                fi
                echo "unexpected fake tenv invocation: $*" >&2
                exit 64
                """
            )
        )
        self.fake_tenv.chmod(0o755)

        self.fake_terragrunt = self.directory / "fake-terragrunt"
        self.fake_terragrunt.write_text(
            textwrap.dedent(
                """\
                #!/bin/sh
                set -eu
                {
                    printf 'root=%s\\n' "${TENV_ROOT:-}"
                    printf 'auto=%s\\n' "${TENV_AUTO_INSTALL:-}"
                    printf 'arch=%s\\n' "${TENV_ARCH:-}"
                    printf 'log=%s\\n' "${TENV_LOG:-}"
                    printf 'no_color=%s\\n' "${NO_COLOR:-}"
                    printf 'token=%s\\n' "${TENV_GITHUB_TOKEN:-}"
                    printf 'args='
                    printf '%s ' "$@"
                    printf '\\n'
                } > "$CAPTURE"
                echo 'terragrunt version v0.54.19'
                """
            )
        )
        self.fake_terragrunt.chmod(0o755)

        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("TENV_") and not key.startswith("TGENV_")
        }
        self.environment.update(
            {
                "HOME": str(self.home),
                "PATH": f"{self.bin}:{os.environ['PATH']}",
                "TENV_BINARY": str(self.fake_tenv),
                "TERRAGRUNT_BINARY": str(self.fake_terragrunt),
                "CAPTURE": str(self.capture),
            }
        )

    def run_command(self, command, *arguments, cwd=None, **environment):
        merged_environment = self.environment | {
            key: str(value) for key, value in environment.items()
        }
        return subprocess.run(
            [str(self.bin / command), *arguments],
            cwd=cwd or self.directory,
            env=merged_environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def captured(self):
        return dict(
            line.split("=", 1) for line in self.capture.read_text().splitlines()
        )

    def install_marker(self, version, *, legacy=False):
        directory = self.home / ".tgenv"
        directory /= "versions" if legacy else "Terragrunt"
        directory /= version
        directory.mkdir(parents=True, exist_ok=True)
        binary = directory / "terragrunt"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        return directory

    def test_preferred_tenv_preserves_upstream_auto_install_default(self):
        result = self.run_command("tenv", "version")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "tenv version v4.14.8")
        self.assertEqual(self.captured()["auto"], "")
        self.assertEqual(self.captured()["root"], str(self.home / ".tgenv"))

    def test_terragrunt_defaults_auto_install_and_maps_legacy_environment(self):
        result = self.run_command(
            "terragrunt",
            "--version",
            TGENV_DATA_DIR=self.directory / "state",
            TGENV_AUTO_INSTALL="false",
            TGENV_ARCH="amd64",
            TGENV_DEBUG="1",
            TGENV_DISABLE_COLOR="1",
            TENV_GITHUB_TOKEN="example-token",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        captured = self.captured()
        self.assertEqual(captured["root"], str(self.directory / "state"))
        self.assertEqual(captured["auto"], "false")
        self.assertEqual(captured["arch"], "amd64")
        self.assertEqual(captured["log"], "trace")
        self.assertEqual(captured["no_color"], "1")
        self.assertEqual(captured["token"], "example-token")

        default_result = self.run_command("terragrunt", "--version")
        self.assertEqual(default_result.returncode, 0, default_result.stderr)
        self.assertEqual(self.captured()["auto"], "true")

        empty_legacy_result = self.run_command(
            "terragrunt", "--version", TGENV_AUTO_INSTALL=""
        )
        self.assertEqual(
            empty_legacy_result.returncode,
            0,
            empty_legacy_result.stderr,
        )
        self.assertEqual(self.captured()["auto"], "true")

    def test_version_output_reports_the_real_backend(self):
        result = self.run_command("tgenv", "--version")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "tgenv compatibility facade (tenv version v4.14.8)",
        )

    def test_install_uses_parent_version_file_without_rewriting_it(self):
        workspace = self.directory / "workspace"
        child = workspace / "nested"
        child.mkdir(parents=True)
        version_file = workspace / ".terragrunt-version"
        version_file.write_text("0.54.19\n")
        version_file.chmod(0o444)

        result = self.run_command("tgenv", "install", cwd=child)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.captured()["args"].strip(), "tg install 0.54.19")
        self.assertEqual(version_file.read_text(), "0.54.19\n")

    def test_version_name_resolves_parent_file_and_latest_across_layouts(self):
        workspace = self.directory / "workspace"
        child = workspace / "nested"
        child.mkdir(parents=True)
        (workspace / ".terragrunt-version").write_text("latest\n")
        self.install_marker("1.9.0", legacy=True)
        self.install_marker("1.10.0")

        result = self.run_command("tgenv", "version-name", cwd=child)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1.10.0")

    def test_list_combines_legacy_and_new_layouts_without_duplicates(self):
        (self.home / ".terragrunt-version").write_text("1.10.0\n")
        self.install_marker("1.9.0", legacy=True)
        self.install_marker("1.10.0", legacy=True)
        self.install_marker("1.10.0")

        result = self.run_command("tgenv", "list")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("1.10.0"), 1)
        self.assertIn("* 1.10.0", result.stdout)
        self.assertIn("  1.9.0", result.stdout)

    def test_list_remote_preserves_descending_stable_contract(self):
        result = self.run_command("tgenv", "list-remote")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.captured()["args"].strip(),
            "tg list-remote --descending --stable",
        )

    def test_use_rewrites_the_discovered_project_version_file(self):
        workspace = self.directory / "workspace"
        child = workspace / "nested"
        child.mkdir(parents=True)
        version_file = workspace / ".terragrunt-version"
        version_file.write_text("1.9.0\n")
        self.install_marker("1.10.0")

        result = self.run_command("tgenv", "use", "1.10.0", cwd=child)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(version_file.read_text(), "1.10.0\n")

    def test_uninstall_removes_new_and_legacy_copies(self):
        new_path = self.install_marker("0.54.19")
        legacy_path = self.install_marker("0.54.19", legacy=True)

        result = self.run_command("tgenv", "uninstall", "0.54.19")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(new_path.exists())
        self.assertFalse(legacy_path.exists())

    def test_upgrade_fails_with_immutable_image_guidance(self):
        result = self.run_command("tgenv", "upgrade")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("use a newer image tag", result.stderr)

    def test_backend_failures_are_not_hidden(self):
        version_file = self.home / ".terragrunt-version"
        version_file.write_text("0.54.19\n")

        result = self.run_command("tgenv", "install", FAIL_TENV=23)

        self.assertEqual(result.returncode, 23)


if __name__ == "__main__":
    unittest.main()
