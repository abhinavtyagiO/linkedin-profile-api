import unittest
from unittest.mock import patch

from linkedin_profile_api.client import LinkedInClient
from linkedin_profile_api.config import LinkedInCredentials


class FakeHeaders:
    @staticmethod
    def get_content_type() -> str:
        return "application/octet-stream"


class FakeResponse:
    headers = FakeHeaders()

    def __init__(self, payload: bytes = b'0:{"ok":true}\n') -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self, _size: int) -> bytes:
        return self.payload


class ClientTests(unittest.TestCase):
    @patch("linkedin_profile_api.client.urllib.request.urlopen")
    def test_requests_a_stable_english_linkedin_locale(self, urlopen):
        urlopen.return_value = FakeResponse()
        client = LinkedInClient(
            LinkedInCredentials(li_at="secret-a", jsessionid="ajax:123")
        )

        client.fetch_base_profile("example-person")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Accept-language"), "en-US,en;q=0.9")
        self.assertIn("lang=v=2&lang=en-us", request.get_header("Cookie"))

    @patch("linkedin_profile_api.client.urllib.request.urlopen")
    def test_retries_one_transient_flight_decode_failure(self, urlopen):
        urlopen.side_effect = [
            FakeResponse(b"temporary non-Flight response"),
            FakeResponse(),
        ]
        client = LinkedInClient(
            LinkedInCredentials(li_at="secret-a", jsessionid="ajax:123")
        )

        stream = client.fetch_base_profile("example-person")

        self.assertEqual(stream.record_count, 1)
        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
