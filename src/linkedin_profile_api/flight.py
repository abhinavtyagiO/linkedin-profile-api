"""Bounded decoder for the React Flight record subset observed on LinkedIn.

This is intentionally not a browser renderer. It indexes newline-delimited
Flight records and resolves the reference forms needed by the captured
LinkedIn Flagship responses while preserving module imports as metadata.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Set, Tuple


_RECORD_ID_BYTES_RE = re.compile(br"^[0-9a-f]+$")
_HEX_LENGTH_BYTES_RE = re.compile(br"^[0-9a-f]+$")
_LAZY_REFERENCE_RE = re.compile(r"^\$L([0-9a-f]+)$")
_COLLECTION_REFERENCE_RE = re.compile(r"^\$[QW]([0-9a-f]+)$")
_PATH_REFERENCE_RE = re.compile(r"^\$([0-9a-f]+):(.+)$")


class FlightDecodeError(ValueError):
    """Raised when a Flight stream is malformed or exceeds safety limits."""


@dataclass(frozen=True)
class FlightLimits:
    max_bytes: int = 2_000_000
    max_records: int = 5_000
    max_line_bytes: int = 500_000
    max_json_depth: int = 128
    max_resolved_nodes: int = 200_000


@dataclass(frozen=True)
class ModuleImport:
    record_id: str
    module_id: str
    dependencies: Tuple[Any, ...]
    export_name: str


@dataclass(frozen=True)
class FlightRecord:
    record_id: str
    tag: str
    raw_body: str
    value: Any

    @property
    def is_import(self) -> bool:
        return self.tag == "I"


@dataclass(frozen=True)
class SymbolReference:
    name: str


@dataclass(frozen=True)
class UnresolvedReference:
    token: str


class _UndefinedValue:
    def __repr__(self) -> str:
        return "UNDEFINED"


UNDEFINED = _UndefinedValue()
REACT_ELEMENT = SymbolReference("react.element")


def _json_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, dict):
        if not value:
            return depth
        return max(_json_depth(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        if not value:
            return depth
        return max(_json_depth(item, depth + 1) for item in value)
    return depth


class FlightStream:
    def __init__(
        self,
        records: Mapping[str, FlightRecord],
        order: Sequence[str],
        limits: FlightLimits,
    ) -> None:
        self._records = dict(records)
        self._order = tuple(order)
        self.limits = limits

    @classmethod
    def parse(
        cls,
        payload: Any,
        limits: Optional[FlightLimits] = None,
    ) -> "FlightStream":
        active_limits = limits or FlightLimits()
        if isinstance(payload, bytes):
            if len(payload) > active_limits.max_bytes:
                raise FlightDecodeError("Flight payload exceeds byte limit")
            try:
                payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise FlightDecodeError("Flight payload is not valid UTF-8") from exc
            data = payload
        elif isinstance(payload, str):
            data = payload.encode("utf-8")
            if len(data) > active_limits.max_bytes:
                raise FlightDecodeError("Flight payload exceeds byte limit")
        else:
            raise TypeError("Flight payload must be bytes or str")

        records: Dict[str, FlightRecord] = {}
        order: List[str] = []
        position = 0
        line_number = 1
        while position < len(data):
            if data[position : position + 2] == b"\r\n":
                position += 2
                line_number += 1
                continue
            if data[position : position + 1] == b"\n":
                position += 1
                line_number += 1
                continue

            record_start = position
            record_line = line_number
            colon = data.find(b":", position)
            if colon < 0:
                raise FlightDecodeError(
                    "Malformed Flight record on line {}".format(record_line)
                )
            record_id_bytes = data[position:colon]
            if not _RECORD_ID_BYTES_RE.fullmatch(record_id_bytes):
                raise FlightDecodeError(
                    "Malformed Flight record on line {}".format(record_line)
                )
            position = colon + 1

            tag = ""
            if position < len(data) and 65 <= data[position] <= 90:
                tag = chr(data[position])
                position += 1

            if tag == "T":
                comma = data.find(b",", position)
                if comma < 0:
                    raise FlightDecodeError(
                        "Malformed text record on line {}".format(record_line)
                    )
                length_bytes = data[position:comma]
                if not _HEX_LENGTH_BYTES_RE.fullmatch(length_bytes):
                    raise FlightDecodeError(
                        "Malformed text record on line {}".format(record_line)
                    )
                text_length = int(length_bytes, 16)
                body_start = comma + 1
                body_end = body_start + text_length
                if body_end > len(data):
                    raise FlightDecodeError(
                        "Truncated text record on line {}".format(record_line)
                    )
                raw_body_bytes = data[body_start:body_end]
                position = body_end
                if data[position : position + 2] == b"\r\n":
                    position += 2
                elif data[position : position + 1] == b"\n":
                    position += 1
            else:
                newline = data.find(b"\n", position)
                if newline < 0:
                    body_end = len(data)
                    position = len(data)
                else:
                    body_end = newline
                    position = newline + 1
                if data[body_end - 1 : body_end] == b"\r":
                    body_end -= 1
                raw_body_bytes = data[colon + 1 + (1 if tag else 0) : body_end]

            if position - record_start > active_limits.max_line_bytes:
                raise FlightDecodeError(
                    "Flight record on line {} exceeds line limit".format(record_line)
                )
            if len(order) >= active_limits.max_records:
                raise FlightDecodeError(
                    "Flight payload exceeds record limit"
                )

            record_id = record_id_bytes.decode("ascii")
            try:
                raw_body = raw_body_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise FlightDecodeError(
                    "Flight record on line {} is not valid UTF-8".format(record_line)
                ) from exc
            if record_id in records:
                raise FlightDecodeError(
                    "Duplicate Flight record id on line {}".format(record_line)
                )

            value = cls._parse_record_value(record_id, tag, raw_body, record_line)
            if _json_depth(value) > active_limits.max_json_depth:
                raise FlightDecodeError(
                    "Flight record on line {} exceeds JSON depth limit".format(
                        record_line
                    )
                )
            records[record_id] = FlightRecord(record_id, tag, raw_body, value)
            order.append(record_id)
            line_number += data[record_start:position].count(b"\n")

        if not records:
            raise FlightDecodeError("Flight payload contains no records")
        return cls(records=records, order=order, limits=active_limits)

    @staticmethod
    def _parse_record_value(
        record_id: str,
        tag: str,
        raw_body: str,
        line_number: int,
    ) -> Any:
        if tag == "T":
            return raw_body
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            if tag:
                raise FlightDecodeError(
                    "Malformed tagged record on line {}".format(line_number)
                )
            return raw_body

        if tag == "I":
            if not isinstance(parsed, list) or len(parsed) < 3:
                raise FlightDecodeError(
                    "Malformed import record on line {}".format(line_number)
                )
            module_id, dependencies, export_name = parsed[:3]
            if not isinstance(module_id, str) or not isinstance(export_name, str):
                raise FlightDecodeError(
                    "Malformed import record on line {}".format(line_number)
                )
            if not isinstance(dependencies, list):
                raise FlightDecodeError(
                    "Malformed import dependencies on line {}".format(line_number)
                )
            return ModuleImport(
                record_id=record_id,
                module_id=module_id,
                dependencies=tuple(dependencies),
                export_name=export_name,
            )
        return parsed

    @property
    def record_count(self) -> int:
        return len(self._records)

    @property
    def import_count(self) -> int:
        return sum(1 for record in self._records.values() if record.is_import)

    @property
    def data_count(self) -> int:
        return self.record_count - self.import_count

    def record(self, record_id: str) -> FlightRecord:
        try:
            return self._records[record_id]
        except KeyError as exc:
            raise FlightDecodeError("Unknown Flight record reference") from exc

    def records(self) -> Iterator[FlightRecord]:
        for record_id in self._order:
            yield self._records[record_id]

    def resolve_record(self, record_id: str) -> Any:
        budget = [self.limits.max_resolved_nodes]
        return self._resolve_record(record_id, active=set(), budget=budget)

    def _resolve_record(
        self,
        record_id: str,
        active: Set[str],
        budget: List[int],
    ) -> Any:
        marker = "record:{}".format(record_id)
        if marker in active:
            raise FlightDecodeError("Cyclic Flight record reference")
        record = self.record(record_id)
        if record.is_import:
            return record.value
        active.add(marker)
        try:
            return self._resolve_value(record.value, active=active, budget=budget)
        finally:
            active.remove(marker)

    def _consume_budget(self, budget: List[int]) -> None:
        budget[0] -= 1
        if budget[0] < 0:
            raise FlightDecodeError("Resolved Flight tree exceeds node limit")

    def _resolve_value(
        self,
        value: Any,
        active: Set[str],
        budget: List[int],
    ) -> Any:
        self._consume_budget(budget)
        if isinstance(value, str):
            if value == "$":
                return REACT_ELEMENT
            if value == "$undefined":
                return UNDEFINED
            if value.startswith("$$"):
                return value[1:]
            if value.startswith("$S"):
                return SymbolReference(value[2:])

            lazy_match = _LAZY_REFERENCE_RE.match(value)
            if lazy_match:
                return self._resolve_record(lazy_match.group(1), active, budget)

            # React Flight encodes Map and Set payloads as $Q/$W references.
            # The referenced record remains a regular bounded list structure;
            # keeping that structure is sufficient for SDUI traversal and does
            # not require emulating JavaScript collection semantics.
            collection_match = _COLLECTION_REFERENCE_RE.match(value)
            if collection_match:
                return self._resolve_record(collection_match.group(1), active, budget)

            path_match = _PATH_REFERENCE_RE.match(value)
            if path_match:
                return self._resolve_path_reference(
                    path_match.group(1),
                    path_match.group(2),
                    active,
                    budget,
                )

            if value.startswith("$"):
                return UnresolvedReference(value)
            return value

        if isinstance(value, list):
            return [
                self._resolve_value(item, active=active, budget=budget)
                for item in value
            ]
        if isinstance(value, dict):
            return {
                key: self._resolve_value(item, active=active, budget=budget)
                for key, item in value.items()
            }
        return value

    def _resolve_path_reference(
        self,
        record_id: str,
        raw_path: str,
        active: Set[str],
        budget: List[int],
    ) -> Any:
        marker = "path:{}:{}".format(record_id, raw_path)
        if marker in active:
            raise FlightDecodeError("Cyclic Flight path reference")

        record = self.record(record_id)
        if record.is_import:
            raise FlightDecodeError("Flight path cannot target an import record")

        # Traverse the raw record first. LinkedIn legitimately points into the
        # record currently being resolved, so resolving the whole record before
        # traversal would misclassify shared subtrees as cycles.
        referenced = self._traverse_path(record.value, raw_path)
        active.add(marker)
        try:
            return self._resolve_value(referenced, active=active, budget=budget)
        finally:
            active.remove(marker)

    @staticmethod
    def _traverse_path(value: Any, raw_path: str) -> Any:
        current = value
        for segment in raw_path.split(":"):
            if isinstance(current, list):
                if current and current[0] == "$" and segment in {
                    "type",
                    "key",
                    "props",
                }:
                    index = {"type": 1, "key": 2, "props": 3}[segment]
                else:
                    try:
                        index = int(segment)
                    except ValueError as exc:
                        raise FlightDecodeError("Invalid list path reference") from exc
                try:
                    current = current[index]
                except IndexError as exc:
                    raise FlightDecodeError("Flight path reference is out of range") from exc
            elif isinstance(current, dict):
                if segment not in current:
                    raise FlightDecodeError("Flight path reference key is missing")
                current = current[segment]
            else:
                raise FlightDecodeError("Flight path reference is not traversable")
        return current

    def find_objects(self, field: str, expected: Any) -> Iterator[Dict[str, Any]]:
        """Yield raw decoded objects that match a field value.

        This intentionally walks the record table without resolving references;
        callers can resolve the owning record after selecting a semantic anchor.
        """

        for record in self.records():
            if record.is_import:
                continue
            yield from _find_objects(record.value, field, expected)


def _find_objects(value: Any, field: str, expected: Any) -> Iterator[Dict[str, Any]]:
    if isinstance(value, dict):
        if value.get(field) == expected:
            yield value
        for item in value.values():
            yield from _find_objects(item, field, expected)
    elif isinstance(value, list):
        for item in value:
            yield from _find_objects(item, field, expected)
