import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MultiArchitectureWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image_ci = (ROOT / ".github/workflows/image_ci.yml").read_text()
        cls.release = (ROOT / ".github/workflows/release.yml").read_text()

    def assert_native_matrix(self, workflow):
        self.assertRegex(
            workflow,
            re.compile(r"- arch: amd64\n\s+runner: ubuntu-24\.04\n"),
        )
        self.assertRegex(
            workflow,
            re.compile(r"- arch: arm64\n\s+runner: ubuntu-24\.04-arm\n"),
        )
        self.assertIn("runs-on: ${{ matrix.runner }}", workflow)

    def test_image_ci_uses_native_runners_and_shared_contract(self):
        self.assert_native_matrix(self.image_ci)
        self.assertIn("platforms: linux/${{ matrix.arch }}", self.image_ci)
        self.assertIn(
            "tests/test-image.sh tf-image-build:ci-${{ matrix.arch }} ${{ matrix.arch }}",
            self.image_ci,
        )

    def test_release_validates_natively_and_publishes_one_manifest(self):
        self.assert_native_matrix(self.release)
        self.assertIn(
            "tests/test-image.sh tf-image-build:release-candidate-${{ matrix.arch }} ${{ matrix.arch }}",
            self.release,
        )
        self.assertEqual(
            self.release.count("platforms: linux/amd64,linux/arm64"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
