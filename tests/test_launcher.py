import os
import pty
import shutil
import socket
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
TF_IMAGE_VARIABLES = (
    "TF_IMAGE_AWS_CONFIG",
    "TF_IMAGE_AWS_ENV",
    "TF_IMAGE_SSH_AGENT",
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
        for name in (*AWS_VARIABLES, *TF_IMAGE_VARIABLES, "SSH_AUTH_SOCK"):
            self.env.pop(name, None)

    def tearDown(self):
        self.tempdir.cleanup()

    def run_launcher(self, *command, tty=False, docker_exit=0):
        self.capture.unlink(missing_ok=True)
        env = self.env | {"DOCKER_EXIT": str(docker_exit)}

        if tty:
            pid, terminal = pty.fork()
            if pid == 0:
                os.chdir(self.workspace)
                os.execve(LAUNCHER, [str(LAUNCHER), *command], env)
            _, status = os.waitpid(pid, 0)
            os.close(terminal)
            returncode = os.waitstatus_to_exitcode(status)
            stderr = ""
        else:
            result = subprocess.run(
                [LAUNCHER, *command],
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
        self.assertIn("--user", arguments)
        user_index = arguments.index("--user")
        self.assertEqual(arguments[user_index + 1], f"{os.getuid()}:{os.getgid()}")
        self.assertIn(f"{os.path.realpath(self.workspace)}:/workspace", arguments)
        self.assertIn(
            f"{self.home}/.cache/tf-image/home:/home/terraform:rw",
            arguments,
        )
        self.assertIn("HOME=/home/terraform", arguments)
        self.assertIn(
            "TF_PLUGIN_CACHE_DIR=/home/terraform/.terraform.d/plugin-cache",
            arguments,
        )
        self.assertFalse(any("/.ssh:" in argument for argument in arguments))
        self.assertFalse(any("/.aws:" in argument for argument in arguments))
        self.assertEqual(arguments[-1], "example/image:test")

    def test_tty_invocation_enables_interactive_mode(self):
        returncode, _, arguments = self.run_launcher(tty=True)

        self.assertEqual(returncode, 0)
        self.assertIn("-it", arguments)

    def test_requested_command_arguments_are_forwarded_after_the_image(self):
        returncode, _, arguments = self.run_launcher(
            "terraform", "fmt", "path with spaces"
        )

        self.assertEqual(returncode, 0)
        self.assertEqual(
            arguments[-4:],
            ["example/image:test", "terraform", "fmt", "path with spaces"],
        )

    def test_credentials_remain_disabled_without_explicit_opt_in(self):
        (self.home / ".ssh").mkdir()
        (self.home / ".aws").mkdir()
        self.env["AWS_REGION"] = "us-west-2"
        self.env["AWS_PROFILE"] = "profile with spaces"

        returncode, _, arguments = self.run_launcher()

        self.assertEqual(returncode, 0)
        self.assertFalse(any("/.ssh:" in argument for argument in arguments))
        self.assertFalse(any("/.aws:" in argument for argument in arguments))
        self.assertNotIn("AWS_REGION=us-west-2", arguments)
        self.assertNotIn("AWS_PROFILE=profile with spaces", arguments)

    def test_aws_environment_opt_in_forwards_only_populated_variables(self):
        self.env["TF_IMAGE_AWS_ENV"] = "1"
        self.env["AWS_REGION"] = "us-west-2"
        self.env["AWS_PROFILE"] = "profile with spaces"

        returncode, _, arguments = self.run_launcher()

        self.assertEqual(returncode, 0)
        self.assertIn("AWS_REGION=us-west-2", arguments)
        self.assertIn("AWS_PROFILE=profile with spaces", arguments)
        self.assertFalse(
            any(argument.startswith("AWS_ACCESS_KEY_ID=") for argument in arguments)
        )

    def test_aws_config_opt_in_mounts_read_only(self):
        (self.home / ".aws").mkdir()
        self.env["TF_IMAGE_AWS_CONFIG"] = "1"

        returncode, _, arguments = self.run_launcher()

        self.assertEqual(returncode, 0)
        self.assertIn(
            f"{self.home}/.aws:/home/terraform/.aws:ro",
            arguments,
        )

    def test_ssh_agent_opt_in_mounts_only_the_agent_socket(self):
        socket_path = self.root / "agent.sock"
        agent_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(agent_socket.close)
        agent_socket.bind(str(socket_path))
        self.env["TF_IMAGE_SSH_AGENT"] = "1"
        self.env["SSH_AUTH_SOCK"] = str(socket_path)

        returncode, _, arguments = self.run_launcher()

        self.assertEqual(returncode, 0)
        self.assertIn(f"{socket_path}:/tmp/tf-image-ssh-agent.sock:ro", arguments)
        self.assertIn("SSH_AUTH_SOCK=/tmp/tf-image-ssh-agent.sock", arguments)
        self.assertFalse(any("/.ssh:" in argument for argument in arguments))

    def test_missing_requested_credential_source_fails_before_docker(self):
        self.env["TF_IMAGE_AWS_CONFIG"] = "1"

        returncode, stderr, arguments = self.run_launcher()

        self.assertNotEqual(returncode, 0)
        self.assertIn("TF_IMAGE_AWS_CONFIG=1", stderr)
        self.assertEqual(arguments, [])

    def test_invalid_opt_in_value_fails_before_docker(self):
        self.env["TF_IMAGE_AWS_ENV"] = "yes"

        returncode, stderr, arguments = self.run_launcher()

        self.assertNotEqual(returncode, 0)
        self.assertIn("TF_IMAGE_AWS_ENV must be 0 or 1", stderr)
        self.assertEqual(arguments, [])

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
        self.home = self.workspace / "home"
        self.bin_dir = self.workspace / "bin"
        self.capture = self.workspace / "docker-arguments"
        self.home.mkdir()
        self.bin_dir.mkdir()
        (self.workspace / ".image").write_text("IMAGE=example/image:test\n")

        launcher = self.workspace / "tf_image"
        shutil.copy2(LAUNCHER, launcher)

        fake_docker = self.bin_dir / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import sys\n"
            "with open(os.environ['DOCKER_CAPTURE'], 'wb') as stream:\n"
            "    stream.write(b'\\0'.join(arg.encode() for arg in sys.argv[1:]))\n"
            "    stream.write(b'\\0')\n"
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
        for name in (*AWS_VARIABLES, *TF_IMAGE_VARIABLES, "SSH_AUTH_SOCK"):
            self.env.pop(name, None)

    def tearDown(self):
        self.tempdir.cleanup()

    def run_ci(self, *arguments):
        self.capture.unlink(missing_ok=True)
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
        self.assertNotIn("-it", arguments)
        image_index = arguments.index("example/image:test")
        self.assertEqual(arguments[image_index + 1 : image_index + 3], ["sh", "-ceu"])
        self.assertIn("tfenv install", arguments[image_index + 3])
        self.assertIn("tgenv install", arguments[image_index + 3])
        self.assertEqual(
            arguments[-5:],
            ["sh", "terraform", "fmt", "-check", "path with spaces"],
        )


if __name__ == "__main__":
    unittest.main()
