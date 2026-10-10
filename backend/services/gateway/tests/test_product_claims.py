import unittest
import os
from unittest.mock import patch

os.environ["APP_PRODUCT"] = "learn"
os.environ["APP_ENV"] = "test"
from app.factory import product_claim_matches
from app.factory import build_app


class GatewayProductClaimTests(unittest.TestCase):
    def test_product_gateway_requires_matching_claim(self):
        self.assertTrue(product_claim_matches({"product": "learn"}, "learn"))
        self.assertFalse(product_claim_matches({"product": "hire"}, "learn"))
        self.assertFalse(product_claim_matches({}, "learn"))  # legacy token

    def test_combined_gateway_keeps_route_policy_optional(self):
        self.assertTrue(product_claim_matches({}, None))

    def test_health_and_bounded_readiness(self):
        client = build_app().test_client()
        self.assertEqual(client.get("/health").status_code, 200)
        with patch("app.factory.requests.get") as get:
            get.return_value.ok = True
            ready = client.get("/ready")
        self.assertEqual(ready.status_code, 200)
        self.assertTrue(ready.get_json()["upstreams"])
        self.assertTrue(all(call.kwargs.get("timeout") == 1.5 for call in get.call_args_list))

    def test_readiness_reports_dependency_failure(self):
        client = build_app().test_client()
        with patch("app.factory.requests.get") as get:
            get.return_value.ok = False
            ready = client.get("/ready")
        self.assertEqual(ready.status_code, 503)
        self.assertIn(False, ready.get_json()["upstreams"].values())


if __name__ == "__main__":
    unittest.main()
