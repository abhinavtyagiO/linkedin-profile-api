import json
import threading
import unittest

from linkedin_profile_api.errors import LinkedInProfileNotFound, LinkedInProtocolError
from linkedin_profile_api.flight import FlightStream
from linkedin_profile_api.service import ProfileService, _with_minimum_page_size


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

    def test_increases_skill_page_size_without_mutating_linkedin_request(self):
        request = {
            "requestedArguments": {
                "payload": {"start": 0, "count": 10, "filter": "ALL"}
            }
        }

        normalized = _with_minimum_page_size(request, 50)

        self.assertEqual(normalized["requestedArguments"]["payload"]["count"], 50)
        self.assertEqual(request["requestedArguments"]["payload"]["count"], 10)

    def test_component_fetches_use_bounded_parallelism(self):
        class ConcurrentClient:
            def __init__(self):
                self.lock = threading.Lock()
                self.barrier = threading.Barrier(3)
                self.active = 0
                self.maximum_active = 0

            def fetch_component(self, _vanity, component_id):
                with self.lock:
                    self.active += 1
                    self.maximum_active = max(self.maximum_active, self.active)
                self.barrier.wait(timeout=2)
                with self.lock:
                    self.active -= 1
                return component_id

        client = ConcurrentClient()
        service = ProfileService(client, max_component_workers=3)
        component_ids = ["one", "two", "three"]

        components = service._fetch_components("example-person", component_ids)

        self.assertEqual(components, {item: item for item in component_ids})
        self.assertEqual(client.maximum_active, 3)


if __name__ == "__main__":
    unittest.main()
