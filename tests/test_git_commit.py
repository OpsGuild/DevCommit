import subprocess
import unittest
from unittest.mock import patch

from devcommit.utils.git import KnownError, commit_changes


class CommitChangesTests(unittest.TestCase):
    @patch("devcommit.utils.git.subprocess.run")
    def test_uses_git_commit_by_default(self, run):
        commit_changes("feat: test", ["--no-verify"], files=["src/a.py"])
        run.assert_called_once_with(["git", "commit", "-m", "feat: test", "--no-verify", "--", "src/a.py"], check=True)

    @patch("devcommit.utils.git.subprocess.run")
    def test_uses_configured_commit_alias(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, "!f() { git commit \"$@\"; }; f\n", ""), None]
        commit_changes("feat: test", [], commit_alias="adeola-commit")
        self.assertEqual(run.call_args_list[0].args[0], ["git", "config", "--get", "alias.adeola-commit"])
        self.assertEqual(run.call_args_list[1].args[0], ["git", "adeola-commit", "-m", "feat: test"])
        self.assertTrue(run.call_args_list[1].kwargs["check"])

    @patch("devcommit.utils.git.subprocess.run")
    def test_rejects_missing_alias(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "")
        with self.assertRaisesRegex(KnownError, "not configured"):
            commit_changes("feat: test", [], commit_alias="missing")

    def test_rejects_unsafe_alias(self):
        with self.assertRaisesRegex(KnownError, "may contain only"):
            commit_changes("feat: test", [], commit_alias="bad;alias")
