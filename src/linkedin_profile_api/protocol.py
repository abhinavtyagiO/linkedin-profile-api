"""Pure builders and discovery helpers for LinkedIn's Flagship protocol."""

from __future__ import annotations

import base64
import os
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Set
from urllib.parse import unquote, urlparse

from .errors import InvalidProfileUrl
from .flight import FlightStream


PROFILE_COMPONENT_PREFIX = "com.linkedin.sdui.generated.profile.dsl.impl."
NOT_FOUND_SCREEN_ID = "com.linkedin.sdui.flagshipnav.infra.NotFound"
ASSIGNMENT_COMPONENT_SUFFIXES = (
    "profileCardsAboveActivity",
    "profileCardsExperienceOnly",
    "profileCardsBelowActivityPart1WithoutExp",
    "profileCardsBelowActivityPart4",
    "profileCardsBelowActivityPart7",
)
_VANITY_RE = re.compile(r"^[A-Za-z0-9._~-]{2,100}$")


@dataclass(frozen=True)
class ProfileTarget:
    vanity_name: str
    canonical_url: str


def parse_profile_url(value: str) -> ProfileTarget:
    try:
        parsed = urlparse(value.strip())
    except (AttributeError, ValueError) as exc:
        raise InvalidProfileUrl("A valid LinkedIn profile URL is required") from exc

    if parsed.scheme.lower() != "https":
        raise InvalidProfileUrl("LinkedIn profile URL must use HTTPS")
    if (parsed.hostname or "").lower() not in {"linkedin.com", "www.linkedin.com"}:
        raise InvalidProfileUrl("URL must point to www.linkedin.com")
    if parsed.username or parsed.password or parsed.port:
        raise InvalidProfileUrl("LinkedIn profile URL contains unsupported authority data")

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) != 2 or parts[0].lower() != "in":
        raise InvalidProfileUrl("URL must have the form https://www.linkedin.com/in/<profile>/")
    vanity = parts[1]
    if not _VANITY_RE.fullmatch(vanity):
        raise InvalidProfileUrl("LinkedIn profile identifier is invalid")
    canonical = "https://www.linkedin.com/in/{}/".format(vanity)
    return ProfileTarget(vanity_name=vanity, canonical_url=canonical)


def build_base_action(vanity: str) -> Dict[str, Any]:
    return {
        "$type": "proto.sdui.actions.core.NavigateToScreen",
        "screenId": "com.linkedin.sdui.flagshipnav.profile.Profile",
        "pageKey": "profile_view_base",
        "presentationStyle": "PresentationStyle_FULL_PAGE",
        "presentation": {
            "$case": "fullPage",
            "fullPage": {
                "$type": "proto.sdui.actions.core.presentation.FullPagePresentation"
            },
        },
        "title": "",
        "url": "/in/{}/".format(vanity),
        "inheritActor": False,
        "colorScheme": "ColorScheme_UNKNOWN",
        "disableScreenGutters": False,
        "shouldHideMobileTopNavBar": False,
        "shouldHideLoadingSpinner": False,
        "replaceCurrentScreen": False,
        "shouldHideMobileTopNavBarDivider": False,
        "clearBackStack": False,
        "screenTitle": [],
        "requestedArguments": {
            "payload": {"vanityName": vanity, "isVanityNameResolved": True},
            "states": [],
            "requestMetadata": {"$type": "proto.sdui.common.RequestMetadata"},
            "screenId": "",
            "knownTemplateIds": [],
        },
    }


def build_component_body(vanity: str) -> Dict[str, Any]:
    return {
        "clientArguments": {
            "payload": {"isSelfView": False, "vanityName": vanity},
            "states": [],
            "requestMetadata": {"$type": "proto.sdui.common.RequestMetadata"},
            "screenId": "com.linkedin.sdui.flagshipnav.profile.Profile",
            "knownTemplateIds": [],
        }
    }


def new_parent_span_id() -> str:
    return base64.b64encode(os.urandom(8)).decode("ascii")


def walk(value: Any) -> Iterator[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def discover_profile_components(stream: FlightStream) -> List[str]:
    discovered: Set[str] = set()
    allowed = set(ASSIGNMENT_COMPONENT_SUFFIXES)
    for record in stream.records():
        if record.is_import:
            continue
        for value in walk(record.value):
            if not isinstance(value, dict):
                continue
            if value.get("$type") != "proto.sdui.actions.core.AsyncComponentRequest":
                continue
            component_id = value.get("newComponentId")
            if not isinstance(component_id, str):
                continue
            if not component_id.startswith(PROFILE_COMPONENT_PREFIX):
                continue
            if component_id.rsplit(".", 1)[-1] in allowed:
                discovered.add(component_id)

    return [
        PROFILE_COMPONENT_PREFIX + suffix
        for suffix in ASSIGNMENT_COMPONENT_SUFFIXES
        if PROFILE_COMPONENT_PREFIX + suffix in discovered
    ]


def is_profile_not_found(stream: FlightStream) -> bool:
    """Recognize LinkedIn's semantic not-found screen in a valid Flight response.

    LinkedIn currently returns HTTP 200 for an unknown vanity name and renders
    the infrastructure NotFound screen. Matching its screen identifier avoids
    relying on localized visible text and preserves missing/malformed profile
    screens as protocol errors.
    """

    for record in stream.records():
        if record.is_import:
            continue
        for value in walk(record.value):
            if not isinstance(value, dict):
                continue
            if value.get("screenId") == NOT_FOUND_SCREEN_ID:
                return True
            if value.get("data-sdui-screen") == NOT_FOUND_SCREEN_ID:
                return True
    return False


def discover_detail_action(stream: FlightStream, detail_name: str) -> Optional[Dict[str, Any]]:
    expected_path = "/details/{}/".format(detail_name)
    for record in stream.records():
        if record.is_import:
            continue
        for value in walk(record.value):
            if not isinstance(value, dict):
                continue
            if value.get("$type") != "proto.sdui.actions.core.NavigateToScreen":
                continue
            if expected_path in value.get("url", ""):
                return value
    return None


def discover_pagination_request(
    stream: FlightStream,
    pager_id: str,
    filter_value: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find a typed pager request, including JSON-string continuations."""

    candidates: List[Dict[str, Any]] = []
    for record in stream.records():
        if record.is_import:
            continue
        for value in walk(record.value):
            candidate: Optional[Dict[str, Any]] = None
            if isinstance(value, dict):
                candidate = value
            elif isinstance(value, str) and "PaginationRequest" in value:
                try:
                    decoded = json.loads(value)
                except json.JSONDecodeError:
                    continue
                if isinstance(decoded, dict):
                    candidate = decoded
            if not candidate:
                continue
            if candidate.get("$type") != "proto.sdui.actions.requests.PaginationRequest":
                continue
            if candidate.get("pagerId") != pager_id:
                continue
            payload = candidate.get("requestedArguments", {}).get("payload", {})
            if filter_value is not None and payload.get("filter") != filter_value:
                continue
            candidates.append(candidate)

    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: int(
            candidate.get("requestedArguments", {}).get("payload", {}).get("start", 0)
        ),
    )
