import unittest

from knowledge.models.document import Document
from knowledge.models.evidence import EvidenceBuilder


class EvidenceRankingTests(unittest.TestCase):
    def test_strong_lexical_match_beats_repeated_generic_words(self):
        query = "Marykay Boomi process issue"
        strong_match = Document(
            id="1",
            source="freshdesk",
            title="Marykay Boomi process failure",
            content="Marykay Boomi process issue.",
            metadata={
                "lexical_score": 1.0,
                "primary_content": "Marykay Boomi process issue.",
            },
        )
        noisy_match = Document(
            id="2",
            source="freshdesk",
            title="Holiday processing guidance",
            content=("Boomi " * 2) + ("process " * 29) + ("issue " * 11),
            metadata={
                "lexical_score": 0.1,
                "primary_content": "Holiday processing guidance.",
            },
        )

        evidence = EvidenceBuilder().build(query, [noisy_match, strong_match])

        self.assertEqual(evidence[0].document.id, "1")
        self.assertIn("hybrid_contribution", evidence[0].score_breakdown)
        self.assertEqual(evidence[0].score_breakdown["complete_match_bonus"], 5.0)
        self.assertEqual(
            evidence[0].score,
            evidence[0].score_breakdown["final_score"]
        )
