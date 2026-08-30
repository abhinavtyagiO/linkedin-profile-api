"""Small authenticated HTTP client for the reverse-engineered endpoints."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

from .config import LinkedInCredentials
from .errors import (
    LinkedInAuthenticationError,
    LinkedInChallenge,
    LinkedInProfileNotFound,
    LinkedInProtocolError,
    LinkedInRateLimited,
    LinkedInUnavailable,
)
from .flight import FlightDecodeError, FlightStream, UNDEFINED
from .protocol import build_base_action, build_component_body, new_parent_span_id


class LinkedInClient:
    base_url = "https://www.linkedin.com"

    def __init__(
        self,
        credentials: LinkedInCredentials,
        timeout: float = 20.0,
        max_response_bytes: int = 2_000_000,
    ) -> None:
        self.credentials = credentials
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes

    def fetch_base_profile(self, vanity: str) -> FlightStream:
        quoted = urllib.parse.quote(vanity, safe="")
        return self._post_flight(
            path="/flagship-web/in/{}/".format(quoted),
            body=build_base_action(vanity),
            vanity=vanity,
            anchor_page_key="d_flagship3_feed",
        )

    def fetch_component(self, vanity: str, component_id: str) -> FlightStream:
        query = urllib.parse.urlencode(
            {
                "componentId": component_id,
                "sduiid": component_id,
                "parentSpanId": new_parent_span_id(),
            }
        )
        return self._post_flight(
            path="/flagship-web/rsc-action/actions/component?{}".format(query),
            body=build_component_body(vanity),
            vanity=vanity,
            anchor_page_key="d_flagship3_profile_view_base",
        )

    def fetch_detail(self, vanity: str, action: Dict[str, Any]) -> FlightStream:
        path = action.get("url")
        if not isinstance(path, str) or not path.startswith("/in/{}/details/".format(vanity)):
            raise LinkedInProtocolError("LinkedIn returned an invalid detail action")
        return self._post_flight(
            path="/flagship-web" + path,
            body=action,
            vanity=vanity,
            anchor_page_key="d_flagship3_profile_view_base",
        )

    def fetch_pagination(
        self,
        vanity: str,
        screen_id: str,
        pagination_request: Dict[str, Any],
    ) -> FlightStream:
        pager_id = pagination_request.get("pagerId")
        requested_arguments = pagination_request.get("requestedArguments")
        if not isinstance(pager_id, str) or not isinstance(requested_arguments, dict):
            raise LinkedInProtocolError("LinkedIn returned an invalid pagination request")
        client_arguments = dict(requested_arguments)
        client_arguments.update(
            {
                "states": [],
                "screenId": screen_id,
                "knownTemplateIds": [],
            }
        )
        body = _json_compatible(
            {
                "pagerId": pager_id,
                "clientArguments": client_arguments,
                "paginationRequest": pagination_request,
            }
        )
        query = urllib.parse.urlencode(
            {"sduiid": pager_id, "parentSpanId": new_parent_span_id()}
        )
        return self._post_flight(
            path="/flagship-web/rsc-action/actions/pagination?{}".format(query),
            body=body,
            vanity=vanity,
            anchor_page_key="d_flagship3_profile_view_base",
        )

    def _post_flight(
        self,
        path: str,
        body: Dict[str, Any],
        vanity: str,
        anchor_page_key: str,
    ) -> FlightStream:
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Cookie": self.credentials.cookie_header,
            "Csrf-Token": self.credentials.csrf_token,
            "Origin": self.base_url,
            "Referer": "{}/in/{}/".format(self.base_url, urllib.parse.quote(vanity, safe="")),
            "X-LI-Anchor-Page-Key": anchor_page_key,
            "X-LI-RSC-Stream": "true",
            "User-Agent": "linkedin-profile-api/0.1",
        }
        request = urllib.request.Request(
            url=self.base_url + path,
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read(self.max_response_bytes + 1)
                content_type = response.headers.get_content_type()
        except urllib.error.HTTPError as exc:
            self._raise_http_error(exc.code)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise LinkedInUnavailable("LinkedIn request failed") from exc

        if len(payload) > self.max_response_bytes:
            raise LinkedInProtocolError("LinkedIn response exceeded the configured limit")
        if content_type in {"text/html", "application/xhtml+xml"}:
            raise LinkedInChallenge("LinkedIn returned an authentication or challenge page")
        try:
            return FlightStream.parse(payload)
        except FlightDecodeError as exc:
            raise LinkedInProtocolError("LinkedIn returned an unknown response format") from exc

    @staticmethod
    def _raise_http_error(status: int) -> None:
        if status in {401, 403}:
            raise LinkedInAuthenticationError("LinkedIn session is invalid or expired")
        if status == 404:
            raise LinkedInProfileNotFound("LinkedIn profile was not found")
        if status in {429, 999}:
            raise LinkedInRateLimited("LinkedIn rate limited the request")
        raise LinkedInUnavailable("LinkedIn returned HTTP {}".format(status))


def _json_compatible(value: Any) -> Any:
    """Match JSON.stringify's treatment of observed undefined values."""

    if value is UNDEFINED or value == "$undefined":
        return None
    if isinstance(value, dict):
        return {
            key: _json_compatible(item)
            for key, item in value.items()
            if item is not UNDEFINED and item != "$undefined"
        }
    if isinstance(value, list):
        return [_json_compatible(item) for item in value]
    return value
