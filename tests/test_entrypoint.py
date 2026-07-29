import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "scripts" / "tf-image-entrypoint"
ENDPOINT = "http://host.docker.internal:18080"


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.curl_log = self.root / "curl-arguments"
        curl = self.bin_dir / "curl"
        curl.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$@\" > \"$CURL_LOG\"\n"
            "exit \"${CURL_EXIT:-0}\"\n"
        )
        curl.chmod(0o755)

        self.env = os.environ.copy()
        self.env.update(
            {
                "PATH": f"{self.bin_dir}{os.pathsep}{self.env['PATH']}",
                "CURL_LOG": str(self.curl_log),
            }
        )
        self.env.pop("AWS_EC2_METADATA_SERVICE_ENDPOINT", None)

    def tearDown(self):
        self.tempdir.cleanup()

    def run_entrypoint(self, **env):
        result = subprocess.run(
            [
                "sh",
                ENTRYPOINT,
                "sh",
                "-c",
                'printf "%s" "${AWS_EC2_METADATA_SERVICE_ENDPOINT-unset}"',
            ],
            env=self.env | env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return result

    def test_imdsv2_user_mode_endpoint_is_exported_to_command(self):
        result = self.run_entrypoint()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, ENDPOINT)
        arguments = self.curl_log.read_text().splitlines()
        self.assertIn("PUT", arguments)
        self.assertIn("X-aws-ec2-metadata-token-ttl-seconds: 60", arguments)
        self.assertIn(f"{ENDPOINT}/latest/api/token", arguments)

    def test_incompatible_endpoint_preserves_standard_imds_fallback(self):
        result = self.run_entrypoint(CURL_EXIT="7")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "unset")

    def test_explicit_endpoint_remains_authoritative(self):
        result = self.run_entrypoint(
            AWS_EC2_METADATA_SERVICE_ENDPOINT="http://explicit.example"
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "http://explicit.example")
        self.assertFalse(self.curl_log.exists())

    def test_container_credential_endpoints_remain_authoritative(self):
        for variable in (
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        ):
            with self.subTest(variable=variable):
                self.curl_log.unlink(missing_ok=True)
                result = self.run_entrypoint(**{variable: "/credentials"})

                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "unset")
                self.assertFalse(self.curl_log.exists())


if __name__ == "__main__":
    unittest.main()
