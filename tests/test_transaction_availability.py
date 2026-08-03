import unittest

from china_housing_monitor.transactions.availability import evaluate_candidate, run_http_probe


class TransactionAvailabilityTest(unittest.TestCase):
    def test_beijing_monthly_resale_page_is_eligible(self):
        result = evaluate_candidate(
            "bj",
            "2026-06",
            "https://example.gov.cn/statistics",
            "2026年6月存量房网上签约 住宅签约套数：16618",
        )

        self.assertEqual(result["status"], "eligible")
        self.assertEqual(result["units"], 16618)

    def test_http_probe_writes_one_record_per_core_city(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            records = run_http_probe("2026-06", directory, fetcher=lambda _: "")

            self.assertEqual(len(records), 34)
            self.assertTrue((__import__("pathlib").Path(directory) / "availability.json").exists())


if __name__ == "__main__":
    unittest.main()
