import json
import unittest
from pathlib import Path

from linkedin_profile_api.extract import (
    EXPERIENCE_ID,
    extract_experience,
    extract_skills_page,
    extract_top_card,
)
from linkedin_profile_api.flight import FlightStream


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_top_card.flight"


def element(tag, props):
    return ["$", tag, None, props]


class ExtractTests(unittest.TestCase):
    def test_extracts_allowlisted_top_card_identity(self):
        name, headline, location, images = extract_top_card(
            FlightStream.parse(FIXTURE.read_bytes())
        )

        self.assertEqual(name, "Example Person")
        self.assertEqual(headline, "Software Engineer")
        self.assertIsNone(location)
        self.assertIsNone(images.profile)

    def test_extracts_and_deduplicates_skill_collection_wrappers(self):
        item = element(
            "div",
            {
                "componentkey": "entity-collection-item-one",
                "children": [
                    element("span", {"children": "Python"}),
                    element(
                        "span",
                        {"textProps": {"children": ["Used at Example Co"]}},
                    ),
                ],
            },
        )
        duplicate_wrapper = element(
            "div",
            {
                "componentKey": "entity-collection-item-one",
                "children": item,
            },
        )
        stream = FlightStream.parse(
            "0:{}\n".format(json.dumps([duplicate_wrapper, item]))
        )

        skills = extract_skills_page(stream)

        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "Python")
        self.assertEqual(skills[0].evidence, ["Used at Example Co"])

    def test_extracts_grouped_and_standalone_experience_layouts(self):
        def text(value):
            return {"textProps": {"children": [value]}}

        grouped = {
            "children": [
                text("Example Group"),
                text("Full-time · 3 yrs"),
                text("Bengaluru, Karnataka, India"),
                text("Senior Engineer"),
                text("Jan 2025 - Present · 1 yr"),
                text("Built a platform"),
                text("Engineer"),
                text("Jan 2023 - Dec 2024 · 2 yrs"),
                text("Hybrid"),
            ]
        }
        standalone = {
            "children": [
                text("Software Developer"),
                text("Example Company · Internship"),
                text("May 2022 - Jun 2022 · 2 mos"),
                text("Remote"),
            ]
        }
        payload = {
            "observabilityIdentifier": EXPERIENCE_ID,
            "initialItems": [{"item": grouped}, {"item": standalone}],
        }
        stream = FlightStream.parse("0:{}\n".format(json.dumps(payload)))

        experience = extract_experience(stream)

        self.assertEqual(
            [item.title for item in experience],
            ["Senior Engineer", "Engineer", "Software Developer"],
        )
        self.assertEqual(
            [item.company for item in experience],
            ["Example Group", "Example Group", "Example Company"],
        )
        self.assertEqual(experience[2].employment_type, "Internship")


if __name__ == "__main__":
    unittest.main()
