import json
import unittest

from linkedin_profile_api.errors import InvalidProfileUrl
from linkedin_profile_api.flight import FlightStream
from linkedin_profile_api.protocol import (
    PROFILE_COMPONENT_PREFIX,
    discover_pagination_request,
    discover_profile_components,
    is_profile_not_found,
    parse_profile_url,
)


class ProtocolTests(unittest.TestCase):
    def test_parses_and_canonicalizes_profile_url(self):
        target = parse_profile_url(
            "https://linkedin.com/in/example-person/?trk=public_profile#about"
        )

        self.assertEqual(target.vanity_name, "example-person")
        self.assertEqual(
            target.canonical_url,
            "https://www.linkedin.com/in/example-person/",
        )

    def test_rejects_non_linkedin_and_ambiguous_urls(self):
        invalid = (
            "http://www.linkedin.com/in/example-person/",
            "https://linkedin.example/in/example-person/",
            "https://www.linkedin.com.evil.example/in/example-person/",
            "https://www.linkedin.com/in/example-person/details/skills/",
            "https://user@www.linkedin.com/in/example-person/",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(InvalidProfileUrl):
                    parse_profile_url(value)

    def test_discovers_only_allowlisted_profile_components(self):
        wanted = PROFILE_COMPONENT_PREFIX + "profileCardsExperienceOnly"
        unwanted = PROFILE_COMPONENT_PREFIX + "browsemapRecommendedEntitySection"
        payload = {
            "children": [
                {
                    "$type": "proto.sdui.actions.core.AsyncComponentRequest",
                    "newComponentId": wanted,
                },
                {
                    "$type": "proto.sdui.actions.core.AsyncComponentRequest",
                    "newComponentId": unwanted,
                },
            ]
        }
        stream = FlightStream.parse("0:{}\n".format(json.dumps(payload)))

        self.assertEqual(discover_profile_components(stream), [wanted])

    def test_discovers_json_string_pagination_continuation(self):
        request = {
            "$type": "proto.sdui.actions.requests.PaginationRequest",
            "pagerId": "example-pager",
            "requestedArguments": {
                "payload": {"start": 10, "filter": "ALL"}
            },
        }
        stream = FlightStream.parse("0:{}\n".format(json.dumps([json.dumps(request)])))

        discovered = discover_pagination_request(
            stream,
            "example-pager",
            "ALL",
        )

        self.assertIsNotNone(discovered)
        self.assertEqual(discovered["requestedArguments"]["payload"]["start"], 10)

    def test_recognizes_semantic_not_found_screen(self):
        stream = FlightStream.parse(
            "0:{}\n".format(
                json.dumps(
                    {
                        "screenId": "com.linkedin.sdui.flagshipnav.infra.NotFound",
                        "children": ["Localized not-found copy could be here"],
                    }
                )
            )
        )

        self.assertTrue(is_profile_not_found(stream))

    def test_does_not_use_error_module_or_visible_text_as_not_found_signal(self):
        stream = FlightStream.parse(
            '1:I["module-id",[],"ErrorPage"]\n'
            + "0:{}\n".format(
                json.dumps(
                    {
                        "screenId": "com.linkedin.sdui.flagshipnav.profile.Profile",
                        "children": ["This page doesn’t exist"],
                    }
                )
            )
        )

        self.assertFalse(is_profile_not_found(stream))


if __name__ == "__main__":
    unittest.main()
