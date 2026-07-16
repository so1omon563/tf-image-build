import os
import pty
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "example_usage" / "tf_image"
CI_RUNNER = ROOT / "example_usage" / "tg_ci.sh"
AWS_VARIABLES = (
    "AWS_DEFAULT_REGION",
    "AWS_PROFILE",
    "AWS_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.home = self.root / "home with spaces"
        self.workspace = self.root / "project with spaces"
        self.bin_dir = self.root / "bin"
        self.capture = self.root / "docker-arguments"
        self.home.mkdir()
        self.workspace.mkdir()
        self.bin_dir.mkdir()
        (self.workspace / ".image").write_text("IMAGE=example/image:test\n")

        fake_docker = self.bin_dir / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import sys\n"
            "with open(os.environ['DOCKER_CAPTURE'], 'wb') as stream:\n"
            "    stream.write(b'\\0'.join(arg.encode() for arg in sys.argv[1:]))\n"
            "    stream.write(b'\\0')\n"
            "raise SystemExit(int(os.environ.get('DOCKER_EXIT', '0')))\n"
        )
        fake_docker.chmod(0o755)

        self.env = os.environ.copy()
        self.env.update(
            {
                "HOME": str(self.home),
                "PATH": f"{self.bin_dir}{os.pathsep}{self.env['PATH']}",
                "DOCKER_CAPTURE": str(self.capture),
            }
        )
        for name in AWS_VARIABLES:
            self.env.pop(name, None)

    def tearDown(self):
        self.tempdir.cleanup()

    def run_launcher(self, *, tty=False, docker_exit=0):
        self.capture.unlink(missing_ok=True)
        env = self.env | {"DOCKER_EXIT": str(docker_exit)}

        if tty:
            pid, terminal = pty.fork()
            if pid == 0:
                os.chdir(self.workspace)
                os.execve(LAUNCHER, [str(LAUNCHER)], env)
            _, status = os.waitpid(pid, 0)
            os.close(terminal)
            returncode = os.waitstatus_to_exitcode(status)
            stderr = ""
        else:
            result = subprocess.run(
                [LAUNCHER],
                cwd=self.workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            returncode = result.returncode
            stderr = result.stderr

        arguments = []
        if self.capture.exists():
            arguments = self.capture.read_bytes().rstrip(b"\0").decode().split("\0")
        return returncode, stderr, arguments

    def test_noninteractive_invocation_preserves_paths_and_omits_optional_inputs(self):
        returncode, _, arguments = self.run_launcher()

        self.assertEqual(returncode, 0)
        self.assertNotIn("-it", arguments)
        self.assertIn(f"{os.path.realpath(self.workspace)}:/workspace", arguments)
        self.assertIn(
            f"{self.home}/.cache/pre-commit:/root/.cache/pre-commit", arguments
        )
        self.assertIn(
            f"{self.home}/.terraform.d/plugin-cache:/root/.terraform.d/plugin-cache:rw",
            arguments,
        )
        self.assertNotIn(f"{self.home}/.ssh:/root/.ssh:ro", arguments)
        self.assertNotIn(f"{self.home}/.aws:/root/.aws:rw", arguments)
        self.assertEqual(arguments[-1], "example/image:test")

    def test_tty_invocation_enables_interactive_mode(self):
        returncode, _, arguments = self.run_launcher(tty=True)

        self.assertEqual(returncode, 0)
        self.assertIn("-it", arguments)

    def test_optional_mounts_and_only_populated_aws_variables_are_forwarded(self):
        (self.home / ".ssh").mkdir()
        (self.home / ".aws").mkdir()
        self.env["AWS_REGION"] = "us-west-2"
        self.env["AWS_PROFILE"] = "profile with spaces"

        returncode, _, arguments = self.run_launcher()

        self.assertEqual(returncode, 0)
        self.assertIn(f"{self.home}/.ssh:/root/.ssh:ro", arguments)
        self.assertIn(f"{self.home}/.aws:/root/.aws:rw", arguments)
        self.assertIn("AWS_REGION=us-west-2", arguments)
        self.assertIn("AWS_PROFILE=profile with spaces", arguments)
        self.assertFalse(
            any(argument.startswith("AWS_ACCESS_KEY_ID=") for argument in arguments)
        )

    def test_docker_failure_is_returned_to_the_caller(self):
        returncode, _, _ = self.run_launcher(docker_exit=42)

        self.assertEqual(returncode, 42)

    def test_missing_image_file_fails_before_docker_is_called(self):
        (self.workspace / ".image").unlink()

        returncode, stderr, arguments = self.run_launcher()

        self.assertNotEqual(returncode, 0)
        self.assertIn(".image is missing", stderr)
        self.assertEqual(arguments, [])

    def test_empty_image_value_fails_before_docker_is_called(self):
        (self.workspace / ".image").write_text("IMAGE=\n")

        returncode, stderr, arguments = self.run_launcher()

        self.assertNotEqual(returncode, 0)
        self.assertIn("IMAGE is not set", stderr)
        self.assertEqual(arguments, [])


class CiRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.capture = self.workspace / "tf-image-arguments"

        launcher = self.workspace / "tf_image"
        launcher.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import sys\n"
            "with open(os.environ['TF_IMAGE_CAPTURE'], 'wb') as stream:\n"
            "    stream.write(b'\\0'.join(arg.encode() for arg in sys.argv[1:]))\n"
            "    stream.write(b'\\0')\n"
        )
        launcher.chmod(0o755)
        self.env = os.environ | {"TF_IMAGE_CAPTURE": str(self.capture)}

    def tearDown(self):
        self.tempdir.cleanup()

    def run_ci(self, *arguments):
        return subprocess.run(
            [CI_RUNNER, *arguments],
            cwd=self.workspace,
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

    def test_requires_a_command(self):
        result = self.run_ci()

        self.assertEqual(result.returncode, 64)
        self.assertIn("Usage: ./tg_ci.sh", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_delegates_command_to_the_existing_launcher(self):
        result = self.run_ci("terraform", "fmt", "-check", "path with spaces")

        self.assertEqual(result.returncode, 0)
        arguments = self.capture.read_bytes().rstrip(b"\0").decode().split("\0")
        self.assertEqual(arguments[:2], ["sh", "-ceu"])
        self.assertIn("tfenv install", arguments[2])
        self.assertIn("tgenv install", arguments[2])
        self.assertEqual(
            arguments[-5:],
            ["sh", "terraform", "fmt", "-check", "path with spaces"],
        )


if __name__ == "__main__":
    unittest.main()
