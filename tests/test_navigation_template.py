import unittest
from pathlib import Path


class NavigationTemplateTest(unittest.TestCase):
    def test_new_first_tier_wraps_instead_of_scrolling(self):
        template = Path("china_housing_monitor/report/templates/header.html").read_text(encoding="utf-8")

        self.assertIn('id="nav-tier-2" class="flex flex-wrap gap-2"', template)
        self.assertNotIn('gap-3 overflow-x-auto whitespace-nowrap scrollbar-none py-0.5">\n                    <div class="flex items-center gap-2 w-16 flex-shrink-0">\n                        <span class="w-1 h-3 rounded-full bg-amber-500">', template)


if __name__ == "__main__":
    unittest.main()
