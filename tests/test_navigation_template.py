import unittest
from pathlib import Path


class NavigationTemplateTest(unittest.TestCase):
    def test_new_first_tier_wraps_instead_of_scrolling(self):
        template = Path("china_housing_monitor/report/templates/header.html").read_text(encoding="utf-8")

        self.assertIn('id="nav-tier-2" class="flex flex-wrap gap-2"', template)
        self.assertNotIn('gap-3 overflow-x-auto whitespace-nowrap scrollbar-none py-0.5">\n                    <div class="flex items-center gap-2 w-16 flex-shrink-0">\n                        <span class="w-1 h-3 rounded-full bg-amber-500">', template)

    def test_neutral_extension_lifecycle_is_optional(self):
        root = Path("china_housing_monitor/report")
        base = (root / "templates/base.html").read_text(encoding="utf-8")
        nav = (root / "static/nav.js").read_text(encoding="utf-8")
        onboarding = (root / "static/onboarding.js").read_text(encoding="utf-8")

        self.assertIn("window.CHMExtensionHost = window.CHMExtensionHost ||", base)
        self.assertIn("CHMExtensionHost.init(defaultCity)", base)
        self.assertIn("CHMExtensionHost.onCityChange(cityId)", nav)
        self.assertIn("getOnboardingStep", onboarding)
        self.assertRegex(onboarding, r"typeof\s+host\.getOnboardingStep\s*!==\s*['\"]function['\"]")

    def test_left_floating_research_entry_is_shown_in_every_new_feature_onboarding(self):
        root = Path("china_housing_monitor/report")
        content = (root / "templates/base.html").read_text(encoding="utf-8")
        onboarding = (root / "static/onboarding.js").read_text(encoding="utf-8")

        entry_id = 'id="sentiment-research-report"'
        self.assertIn(entry_id, content)
        self.assertIn('id="chm-floating-entry-rail"', content)
        self.assertIn('fixed left-0 top-1/2', content)
        self.assertLess(content.index('id="map-trigger-tag"'), content.index(entry_id))
        self.assertIn('rounded-r-xl', content[content.index(entry_id):])
        self.assertIn('https://opc-mind.top/blog/chm-sentiment-analysis-2026-09-13/', content)
        self.assertIn('首期城市观察哨调研报告', content)
        self.assertIn("title: '首期城市观察哨调研报告'", onboarding)
        self.assertIn('不定期整理城市观察过程中发现的有趣数据', onboarding)
        self.assertNotIn('右侧腰线', onboarding)
        self.assertIn("highlight: 'sentiment-research-report'", onboarding)
        self.assertIn("const ONBOARDING_VERSION = '5';", onboarding)
        self.assertIn('const FEATURE_STEPS = [RESEARCH_REPORT_STEP];', onboarding)
        self.assertRegex(onboarding, r"activeSteps\s*=\s*selectedMode\s*===\s*'feature'[\s\S]*FEATURE_STEPS[\s\S]*extensionSteps")


if __name__ == "__main__":
    unittest.main()
