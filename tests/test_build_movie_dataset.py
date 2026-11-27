import unittest

from scripts.build_movie_dataset import non_substantive_reason, relevant_rule


class MovieRelevanceTests(unittest.TestCase):
    def row(self, text="", title="", description=""):
        return {
            "post_text": text,
            "embedded_title": title,
            "embedded_description": description,
        }

    def test_odyssey_requires_film_evidence_not_a_generic_journey(self):
        self.assertEqual(
            relevant_rule(
                "the_odyssey",
                self.row("Christopher Nolan's The Odyssey trailer looks incredible."),
            ),
            "odyssey_title_plus_film_context",
        )
        self.assertEqual(
            relevant_rule(
                "the_odyssey",
                self.row("My odyssey through Greece was unforgettable."),
            ),
            "",
        )

    def test_negative_movie_opinion_is_relevant_not_sentiment_filtered(self):
        self.assertEqual(
            relevant_rule(
                "the_odyssey",
                self.row("I watched The Odyssey and hated the pacing."),
            ),
            "odyssey_title_plus_film_context",
        )

    def test_spider_man_full_title_and_common_alias_are_recognized(self):
        self.assertEqual(
            relevant_rule(
                "spider_man_brand_new_day",
                self.row("Spider-Man: Brand New Day teaser is here."),
            ),
            "brand_new_day_title_alias",
        )
        self.assertEqual(
            relevant_rule(
                "spider_man_brand_new_day",
                self.row("Spider-Man 4 trailer looks great."),
            ),
            "brand_new_day_title_alias",
        )
        self.assertEqual(
            relevant_rule(
                "spider_man_brand_new_day",
                self.row("I hope today is a brand new day."),
            ),
            "",
        )

    def test_moana_rule_distinguishes_live_action_from_original_film(self):
        self.assertEqual(
            relevant_rule(
                "moana_live_action",
                self.row("Catherine Laga'aia stars as Moana in the live-action remake."),
            ),
            "moana_title_plus_live_action_context",
        )
        self.assertEqual(
            relevant_rule(
                "moana_live_action",
                self.row("I watched Moana again with my family."),
            ),
            "",
        )
        self.assertEqual(
            relevant_rule(
                "moana_live_action",
                self.row("The Moana 2026 trailer looks great."),
            ),
            "moana_title_plus_2026_film_context",
        )

    def test_only_feed_attribution_and_standalone_links_are_flagged(self):
        self.assertEqual(
            non_substantive_reason(
                {"post_text": 'Feed: "Variety"\nBy: Staff on Friday'}
            ),
            "feed_attribution_only",
        )
        self.assertEqual(
            non_substantive_reason(
                {"post_text": "www.example.com/review"}
            ),
            "bare_link_only",
        )
        self.assertEqual(
            non_substantive_reason(
                {"post_text": "Feed: Variety\nThe movie's visuals were fantastic."}
            ),
            "",
        )
        self.assertEqual(
            non_substantive_reason(
                {"post_text": "I went to see the movie and loved it."}
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
