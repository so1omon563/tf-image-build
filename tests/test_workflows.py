import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MultiArchitectureWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image_ci = (ROOT / ".github/workflows/image_ci.yml").read_text()
        cls.release = (ROOT / ".github/workflows/release.yml").read_text()
        cls.dependency_audit = (
            ROOT / ".github/workflows/dependency_audit.yml"
        ).read_text()
        cls.dependabot = (ROOT / ".github/dependabot.yml").read_text()

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

    def test_release_intent_supports_every_github_merge_strategy(self):
        self.assertIn(
            "release_requested: ${{ steps.release-intent.outputs.requested }}",
            self.release,
        )
        self.assertIn(
            "PR_TITLE: ${{ github.event.pull_request.title }}",
            self.release,
        )
        self.assertIn(
            "#(release|publish|ship)([[:space:]]|$)",
            self.release,
        )

    def test_dependabot_has_bounded_action_and_docker_queues(self):
        self.assertIn("package-ecosystem: github-actions", self.dependabot)
        self.assertIn("package-ecosystem: docker", self.dependabot)
        self.assertIn("actions-minor-patch:", self.dependabot)
        self.assertEqual(self.dependabot.count("interval: weekly"), 2)
        self.assertIn("open-pull-requests-limit: 2", self.dependabot)
        self.assertIn("open-pull-requests-limit: 1", self.dependabot)

    def test_dependabot_keeps_supported_ubuntu_base(self):
        docker_config = self.dependabot.split(
            "package-ecosystem: docker", maxsplit=1
        )[1]
        self.assertIn("dependency-name: ubuntu", docker_config)
        self.assertRegex(docker_config, re.compile(r'versions:\n\s+- "> 24\.04"'))

    def test_manual_dependency_audit_maintains_one_issue(self):
        self.assertIn('cron: "23 13 * * 3"', self.dependency_audit)
        self.assertIn("issues: write", self.dependency_audit)
        self.assertIn("tools/dependency_audit.py", self.dependency_audit)
        self.assertIn("|| audit_status=$?", self.dependency_audit)
        self.assertLess(
            self.dependency_audit.index('cat dependency-audit.md'),
            self.dependency_audit.index('exit "$audit_status"'),
        )
        self.assertIn(
            "Dependency audit: manual pins need review",
            self.dependency_audit,
        )


if __name__ == "__main__":
    unittest.main()
