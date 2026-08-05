from __future__ import annotations

import unittest

from rulemerger.rules import (
    RuleError,
    parse_payload,
    rule_to_classical,
    rule_to_sing_box,
)


class RuleTests(unittest.TestCase):
    def test_classical_rules_preserve_keyword_and_regex_semantics(self) -> None:
        rules = parse_payload(
            "DOMAIN,Example.COM\nDOMAIN-SUFFIX,example.org\nDOMAIN-KEYWORD,cdn\nDOMAIN-REGEX,^api\\.example\\.com$\n",
            "text",
            "classical",
        )

        self.assertEqual(
            [rule.kind for rule in rules],
            ["domain", "domain_suffix", "domain_keyword", "domain_regex"],
        )
        self.assertEqual(rule_to_classical(rules[0]), "DOMAIN,example.com")
        self.assertEqual(rule_to_sing_box(rules[2]), {"domain_keyword": ["cdn"]})

    def test_invalid_rule_is_reported_instead_of_silently_dropped(self) -> None:
        with self.assertRaises(RuleError):
            parse_payload("DOMAIN,not a domain\n", "text", "classical")

    def test_logical_sing_box_rule_is_rejected_without_semantic_loss(self) -> None:
        with self.assertRaisesRegex(RuleError, "AND/OR semantics"):
            parse_payload(
                {
                    "rules": [
                        {
                            "type": "logical",
                            "mode": "and",
                            "rules": [{"domain": ["example.com"]}],
                        }
                    ]
                },
                "json",
                "sing-box",
            )


if __name__ == "__main__":
    unittest.main()
