#!/usr/bin/env python3
"""Exercise the installed image's Python security fixes and ordinary config writes."""

import ssl
import subprocess
import tempfile
import unittest
from importlib.metadata import version
from pathlib import Path

import certifi
import pip._vendor.certifi as pip_certifi
from git import Repo
from packaging.version import Version


class PythonSecurityTests(unittest.TestCase):
    def test_installed_security_floors(self):
        for package, minimum in (("GitPython", "3.2.1"), ("certifi", "2026.10.19")):
            with self.subTest(package=package):
                installed = version(package)
                print(f"{package}={installed}")
                self.assertGreaterEqual(Version(installed), Version(minimum))

    def test_compromised_emsign_root_is_not_trusted(self):
        # Ubuntu's pip uses the system CA bundle rather than installed certifi.
        bundles = {
            "certifi": certifi.where(),
            "system": "/etc/ssl/certs/ca-certificates.crt",
            "pip": pip_certifi.where(),
        }
        for name, bundle in bundles.items():
            with self.subTest(bundle=name):
                context = ssl.create_default_context(cafile=bundle)
                names = {
                    value
                    for certificate in context.get_ca_certs()
                    for rdn in certificate["subject"]
                    for key, value in rdn
                    if key == "commonName"
                }
                self.assertTrue(names, "the CA bundle must retain legitimate trust roots")
                self.assertNotIn("emSign ECC Root CA - G3", names)

    def test_config_write_preserves_dormant_values(self):
        # Check both an on-disk value and the include-file path into the parser.
        # No hook is created or executed; real Git detects any injected directive.
        for included in (False, True):
            with self.subTest(included=included), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo = Repo.init(root / "repo")
                config = Path(repo.git_dir) / "config"
                payload = '[core]\n\tzzz = "A\\nhooksPath = /tmp/untrusted-hooks\\\n"\n'
                if included:
                    extra = root / "included.config"
                    extra.write_text(payload)
                    with config.open("a") as output:
                        output.write(f'[include]\n\tpath = {extra}\n')
                else:
                    with config.open("a") as output:
                        output.write(payload)

                def hooks_path():
                    return subprocess.run(
                        ["git", "-C", str(repo.working_tree_dir), "config", "--get", "core.hooksPath"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                self.assertEqual(hooks_path().returncode, 1)
                with repo.config_writer() as writer:
                    writer.set_value("user", "name", "Image contract")
                result = hooks_path()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(repo.git.config("--get", "user.name"), "Image contract")
                self.assertIn("hooksPath = /tmp/untrusted-hooks", repo.git.config("--get", "core.zzz"))
                repo.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
