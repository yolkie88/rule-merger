from __future__ import annotations

import unittest

from rulemerger.rules import (
    RuleError,
    parse_payload,
    project_rule_for_sing_box,
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

    def test_native_mihomo_rules_are_preserved_and_projected_for_sing_box(self) -> None:
        rules = parse_payload(
            "DOMAIN-WILDCARD,*.example.com\n"
            "PROCESS-NAME,curl\n"
            "IP-ASN,13335\n"
            "DOMAIN,adv0*.example.net\n",
            "text",
            "classical",
        )

        self.assertEqual(
            [rule.kind for rule in rules],
            ["domain_wildcard", "process_name", "ip_asn", "domain_wildcard"],
        )
        self.assertEqual(rule_to_classical(rules[1]), "PROCESS-NAME,curl")
        self.assertEqual(rule_to_classical(rules[2]), "IP-ASN,13335")
        self.assertEqual(rule_to_sing_box(rules[1]), {"process_name": ["curl"]})
        self.assertEqual(
            project_rule_for_sing_box(rules[0]).value,
            "^.*\\.example\\.com$",
        )
        self.assertIsNone(project_rule_for_sing_box(rules[2]))

    def test_sukka_marker_is_not_treated_as_a_domain_rule(self) -> None:
        self.assertEqual(
            parse_payload(
                "this_ruleset_is_made_by_sukkaw.ruleset.skk.moe\n",
                "text",
                "domain",
            ),
            [],
        )

    def test_suffix_glob_is_projected_to_a_portable_regex(self) -> None:
        rule = parse_payload("+.adv0*.example.net\n", "text", "domain")[0]
        self.assertEqual(rule.kind, "domain_regex")
        self.assertEqual(rule.value, r"^(?:.*\.)?adv0.*\.example\.net$")
        self.assertEqual(
            parse_payload(
                "DOMAIN,this_ruleset_is_made_by_sukkaw.ruleset.skk.moe\n",
                "text",
                "classical",
            ),
            [],
        )
        self.assertEqual(
            parse_payload(
                "DOMAIN,7h15.ru1353t.1s.m4d3.by.5ukk4w.skk.moe\n",
                "text",
                "classical",
            ),
            [],
        )

    def test_fully_qualified_domain_is_normalized(self) -> None:
        self.assertEqual(
            parse_payload("+.stat.tiara.\n", "text", "domain")[0].value,
            "stat.tiara",
        )

    def test_non_dns_suffix_is_preserved_as_a_portable_regex(self) -> None:
        rule = parse_payload("+.countly-\n", "text", "domain")[0]
        self.assertEqual(rule.kind, "domain_regex")
        self.assertEqual(rule.value, r"^(?:.*\.)?countly\-$")

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
