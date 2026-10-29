import os
import tempfile
import unittest

from helpers import make_skill, write
import listing_cost
from skillmd import read_frontmatter


class ListingCostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.installed = os.path.join(self.tmp.name, "installed")
        self.cand = os.path.join(self.tmp.name, "cand")
        make_skill(self.installed, "alpha", "A" * 100)
        make_skill(self.installed, "beta", "B" * 100)
        os.makedirs(os.path.join(self.installed, "not-a-skill"))
        make_skill(self.cand, "newbie", "N" * 50)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reports_added_chars(self):
        out = listing_cost.listing_cost(self.cand, self.installed, 10000)
        self.assertEqual(out["installed_count"], 2)
        self.assertEqual(out["chars_added"], len("newbie") + 50 + 4)
        self.assertFalse(out["over_budget"])
        self.assertEqual(out["pushed_out_estimate"], [])

    def test_names_skills_past_budget(self):
        # alpha 109 + beta 108 = 217 fits 220; adding newbie (60) pushes beta out.
        out = listing_cost.listing_cost(self.cand, self.installed, 220)
        self.assertTrue(out["over_budget"])
        self.assertFalse(out["already_over_budget"])
        self.assertEqual(out["pushed_out_estimate"], ["beta"])

    def test_does_not_blame_candidate_for_existing_overflow(self):
        # 217 is already past 200, so beta was out before the candidate.
        out = listing_cost.listing_cost(self.cand, self.installed, 200)
        self.assertTrue(out["already_over_budget"])
        self.assertEqual(out["already_past_budget_count"], 1)
        self.assertEqual(out["pushed_out_estimate"], [])

    def test_frontmatter_forms(self):
        path = os.path.join(self.tmp.name, "f", "SKILL.md")
        write(path, '---\nname: "quoted"\ndescription: >\n  folded line one\n  line two\nother: x\n---\n')
        fm = read_frontmatter(path)
        self.assertEqual(fm["name"], "quoted")
        self.assertEqual(fm["description"], "folded line one line two")
        self.assertEqual(fm["other"], "x")
        write(path, "---\nname: wrapped\ndescription: first line\n  continues here\n---\n")
        self.assertEqual(read_frontmatter(path)["description"], "first line continues here")
        write(path, "no frontmatter here\n")
        self.assertEqual(read_frontmatter(path), {})


if __name__ == "__main__":
    unittest.main()
