import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from sync import apply_rewrites, iter_rules  # noqa: E402


class RewriteRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = [
            {"server": "/home/user/.claude/projects", "mac": "/Users/user/.claude/projects"},
            {"server": "-var-tmp-vibe", "mac": "-private-var-folders-vibe"},
            {"server": "-var-tmp", "mac": "-private-var"},
        ]

    def test_apply_rewrites_server_to_mac(self) -> None:
        content = (
            "/home/user/.claude/projects/-var-tmp-vibe-kanban\n"
            "link:-var-tmp\n"
        )
        expected = (
            "/Users/user/.claude/projects/-private-var-folders-vibe-kanban\n"
            "link:-private-var\n"
        )
        self.assertEqual(
            expected, apply_rewrites(content, self.rules, "server_to_mac")
        )

    def test_apply_rewrites_mac_to_server(self) -> None:
        content = (
            "/Users/user/.claude/projects/-private-var-folders-vibe-kanban\n"
            "link:-private-var\n"
        )
        expected = (
            "/home/user/.claude/projects/-var-tmp-vibe-kanban\n"
            "link:-var-tmp\n"
        )
        self.assertEqual(
            expected, apply_rewrites(content, self.rules, "mac_to_server")
        )

    def test_iter_rules_prefers_longer_matches(self) -> None:
        ordered = list(iter_rules(self.rules, "server_to_mac"))
        sources = [source for source, _ in ordered]
        self.assertLess(
            sources.index("-var-tmp-vibe"),
            sources.index("-var-tmp"),
            "more specific patterns should be applied before broad ones",
        )


if __name__ == "__main__":
    unittest.main()
