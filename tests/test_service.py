import json
import unittest

from linkedin_profile_api.errors import LinkedInProfileNotFound, LinkedInProtocolError
from linkedin_profile_api.flight import FlightStream
from linkedin_profile_api.service import ProfileService


class FakeClient:
    def __init__(self, base_stream: FlightStream) -> None:
        self.base_stream = base_stream
        self.component_requested = False

    def fetch_base_profile(self, _vanity: str) -> FlightStream:
        return self.base_stream

    def fetch_component(self, _vanity: str, _component_id: str) -> FlightStream:
        self.component_requested = True
        raise AssertionError("component calls must not run for a missing profile")


class ServiceTests(unittest.TestCase):
    def test_not_found_screen_stops_before_component_requests(self):
        stream = FlightStream.parse(
            "0:{}\n".format(
                json.dumps(
                    {"screenId": "com.linkedin.sdui.flagshipnav.infra.NotFound"}
                )
            )
        )
        client = FakeClient(stream)

        with self.assertRaises(LinkedInProfileNotFound):
            ProfileService(client).fetch(
                "https://www.linkedin.com/in/missing-profile/"
            )

        self.assertFalse(client.component_requested)

    def test_missing_top_card_without_not_found_screen_remains_protocol_error(self):
        stream = FlightStream.parse(
            "0:{}\n".format(
                json.dumps(
                    {"screenId": "com.linkedin.sdui.flagshipnav.profile.Profile"}
                )
            )
        )

        with self.assertRaises(LinkedInProtocolError):
            ProfileService(FakeClient(stream)).fetch(
                "https://www.linkedin.com/in/malformed-profile/"
            )


if __name__ == "__main__":
    unittest.main()
