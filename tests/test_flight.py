import unittest
from pathlib import Path

from linkedin_profile_api.flight import (
    FlightDecodeError,
    FlightLimits,
    FlightStream,
    ModuleImport,
    REACT_ELEMENT,
    SymbolReference,
    UNDEFINED,
)


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_top_card.flight"


class FlightStreamTests(unittest.TestCase):
    def test_parses_record_table(self):
        stream = FlightStream.parse(FIXTURE.read_bytes())

        self.assertEqual(stream.record_count, 3)
        self.assertEqual(stream.import_count, 1)
        self.assertEqual(stream.data_count, 2)
        self.assertIsInstance(stream.record("1").value, ModuleImport)

    def test_resolves_observed_reference_forms(self):
        stream = FlightStream.parse(FIXTURE.read_bytes())
        resolved = stream.resolve_record("0")

        self.assertEqual(resolved[0], REACT_ELEMENT)
        self.assertIsInstance(resolved[1], ModuleImport)
        top_card = resolved[3]["children"]
        self.assertEqual(
            top_card[3]["children"][1][3]["children"],
            "Software Engineer",
        )
        self.assertEqual(top_card[3]["sharedName"], "Example Person")
        self.assertEqual(top_card[3]["sharedHeadline"], "Software Engineer")
        self.assertIs(resolved[3]["missing"], UNDEFINED)
        self.assertEqual(resolved[3]["literal"], "$amount")
        self.assertEqual(resolved[3]["shared"], "Example Person")
        self.assertEqual(resolved[3]["fragment"], SymbolReference("react.fragment"))

    def test_finds_semantic_anchor_without_resolving(self):
        stream = FlightStream.parse(FIXTURE.read_bytes())
        matches = list(
            stream.find_objects(
                "observabilityIdentifier",
                "com.linkedin.sdui.impl.profile.components.topCard",
            )
        )
        self.assertEqual(len(matches), 1)

    def test_rejects_duplicate_record_ids(self):
        with self.assertRaises(FlightDecodeError):
            FlightStream.parse('0:null\n0:null\n')

    def test_enforces_record_limit(self):
        with self.assertRaises(FlightDecodeError):
            FlightStream.parse(
                '0:null\n1:null\n',
                limits=FlightLimits(max_records=1),
            )

    def test_rejects_cyclic_lazy_reference(self):
        stream = FlightStream.parse('0:"$L1"\n1:"$L0"\n')
        with self.assertRaises(FlightDecodeError):
            stream.resolve_record("0")

    def test_resolves_observed_collection_references(self):
        stream = FlightStream.parse('0:{"map":"$Q1","set":"$W2"}\n1:[["a",1]]\n2:["b"]\n')

        resolved = stream.resolve_record("0")

        self.assertEqual(resolved["map"], [["a", 1]])
        self.assertEqual(resolved["set"], ["b"])


if __name__ == "__main__":
    unittest.main()
