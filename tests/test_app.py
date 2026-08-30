import unittest

from fastapi.testclient import TestClient

from linkedin_profile_api.app import create_app
from linkedin_profile_api.errors import InvalidProfileUrl, LinkedInProfileNotFound
from linkedin_profile_api.models import ProfileResponse


class FakeService:
    def fetch(self, profile_url: str) -> ProfileResponse:
        if "invalid" in profile_url:
            raise InvalidProfileUrl("invalid test URL")
        if "missing" in profile_url:
            raise LinkedInProfileNotFound("LinkedIn profile was not found")
        return ProfileResponse(
            profile_url="https://www.linkedin.com/in/example-person/",
            vanity_name="example-person",
            name="Example Person",
            headline="Engineer",
        )


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(FakeService()))

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_fetch_profile_contract(self):
        response = self.client.post(
            "/v1/profiles:fetch",
            json={"profile_url": "https://www.linkedin.com/in/example-person/"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Example Person")
        self.assertNotIn("about", response.json())
        self.assertNotIn("images", response.json())
        self.assertNotIn("experience", response.json())
        self.assertNotIn("education", response.json())
        self.assertNotIn("skills", response.json())
        self.assertNotIn("certifications", response.json())
        self.assertNotIn("languages", response.json())
        self.assertNotIn("completeness", response.json()["metadata"])
        self.assertNotIn("warnings", response.json()["metadata"])

    def test_stable_service_error(self):
        response = self.client.post(
            "/v1/profiles:fetch",
            json={"profile_url": "invalid"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "invalid_profile_url")

    def test_stable_request_validation_error(self):
        response = self.client.post("/v1/profiles:fetch", json={})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {
                "code": "invalid_request",
                "message": "Request body is invalid",
                "retryable": False,
            },
        )

    def test_profile_not_found_response_contract(self):
        response = self.client.post(
            "/v1/profiles:fetch",
            json={"profile_url": "https://www.linkedin.com/in/missing-profile/"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "code": "profile_not_found",
                "message": "LinkedIn profile was not found",
                "retryable": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
