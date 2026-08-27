import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from china_housing_monitor.report import generator


class ReportOnlyCliTest(unittest.TestCase):
    def test_generated_report_exposes_the_neutral_extension_contract_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "chm.html"
            with (
                patch.object(generator, "REPORT_PATH", str(report_path)),
                patch.object(generator, "fetch_data_payload", return_value={}),
            ):
                generator.generate_html_report()

            html = report_path.read_text(encoding="utf-8")

        for marker in (
            "<!-- CHM_EXTENSION_STYLES -->",
            "<!-- CHM_EXTENSION_CONTENT -->",
            "<!-- CHM_EXTENSION_SCRIPTS -->",
        ):
            self.assertEqual(html.count(marker), 1, marker)
        positions = [
            html.index("<!-- CHM_EXTENSION_STYLES -->"),
            html.index("<!-- CHM_EXTENSION_CONTENT -->"),
            html.index("<!-- CHM_EXTENSION_SCRIPTS -->"),
        ]
        self.assertEqual(positions, sorted(positions))
        last_style_open = html.rfind("<style", 0, positions[0])
        last_style_close = html.rfind("</style>", 0, positions[0])
        self.assertGreater(last_style_close, last_style_open)
        hosts = re.findall(
            r'<div\b(?=[^>]*\bid="chm-extension-host")(?=[^>]*\bdata-chm-extension-host(?:\s|>))[^>]*>',
            html,
        )
        self.assertEqual(len(hosts), 1)


if __name__ == "__main__":
    unittest.main()
