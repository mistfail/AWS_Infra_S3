import unittest

from scripts.scan_s3 import merge_discovered_buckets


class ScanS3Tests(unittest.TestCase):
    def test_merge_adds_new_buckets_and_updates_existing(self) -> None:
        existing_reference = {
            "buckets": [
                {
                    "name": "existing-bucket",
                    "account_id": "111111111111",
                    "account_name": "dev",
                    "first_seen_at": "2024-01-01T00:00:00+00:00",
                    "last_seen_at": "2024-01-01T00:00:00+00:00",
                }
            ]
        }

        discovered_buckets = [
            {
                "name": "existing-bucket",
                "account_id": "111111111111",
                "account_name": "dev",
            },
            {
                "name": "new-bucket",
                "account_id": "222222222222",
                "account_name": "prod",
            },
        ]

        merged = merge_discovered_buckets(existing_reference, discovered_buckets, "2024-02-01T00:00:00+00:00")

        self.assertEqual(len(merged["buckets"]), 2)
        existing_entry = next(entry for entry in merged["buckets"] if entry["name"] == "existing-bucket")
        self.assertEqual(existing_entry["last_seen_at"], "2024-02-01T00:00:00+00:00")
        new_entry = next(entry for entry in merged["buckets"] if entry["name"] == "new-bucket")
        self.assertEqual(new_entry["first_seen_at"], "2024-02-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
