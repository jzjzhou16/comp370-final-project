import importlib
import unittest


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module("carneynews.screening")
        except ModuleNotFoundError:
            self.fail("Relevance screening has not been implemented")

    def test_named_subject_in_lead_is_prioritized_without_final_human_label(self):
        result = self.module.screen("Clinton names a global leader", "Clinton said Mark Carney articulates a vision for allied nations.")
        self.assertEqual(result["screening_hint"], "priority_review")
        self.assertEqual(result["eligibility"], "")

    def test_background_only_reference_requires_review_even_with_name_present(self):
        result = self.module.screen("Bell message surprises traveller", "A traveller described a roaming message. For context, Mark Carney previously discussed recognition of Palestine.")
        self.assertEqual(result["screening_hint"], "needs_focus_review")

    def test_incidental_subject_is_held_for_screening_instead_of_labeled_neutral(self):
        result = self.module.screen("Hockey federation website hacked", "Russia's tournament participation was discussed by the hockey federation.")
        self.assertEqual(result["screening_hint"], "no_subject_in_excerpt")
        self.assertEqual(result["eligibility"], "")

    def test_carney_substring_is_not_a_subject_match(self):
        result = self.module.screen("A town called Carneyville", "The town held a festival.")
        self.assertEqual(result["screening_hint"], "no_subject_in_excerpt")

    def test_policy_explicitly_attributed_to_government_is_detected(self):
        result = self.module.screen("New housing policy announced", "The Carney government announced a housing policy today.")
        self.assertEqual(result["screening_hint"], "priority_review")


if __name__ == "__main__":
    unittest.main()
