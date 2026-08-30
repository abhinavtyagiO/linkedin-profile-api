#!/usr/bin/env python3
"""Secret-safe probe for the confirmed base-profile Flagship request.

The probe intentionally prints metadata only. It never prints credentials,
request headers, response bodies, or normalized profile values.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from linkedin_profile_api.config import ConfigurationError, LinkedInCredentials
from linkedin_profile_api.flight import FlightDecodeError, FlightStream


def build_body(vanity: str) -> bytes:
    body = {
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
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def build_request(vanity: str, credentials: LinkedInCredentials) -> urllib.request.Request:
    safe_vanity = urllib.parse.quote(vanity, safe="")
    url = "https://www.linkedin.com/flagship-web/in/{}/".format(safe_vanity)
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Cookie": credentials.cookie_header,
        "Csrf-Token": credentials.csrf_token,
        "Origin": "https://www.linkedin.com",
        "Referer": "https://www.linkedin.com/in/{}/".format(safe_vanity),
        "X-LI-Anchor-Page-Key": "d_flagship3_feed",
        "X-LI-Initial-URL": "/feed/",
        "X-LI-RSC-Stream": "true",
        "User-Agent": "linkedin-profile-api-research/0.1",
    }
    return urllib.request.Request(
        url=url,
        data=build_body(vanity),
        headers=headers,
        method="POST",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("vanity", help="LinkedIn profile vanity identifier")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        credentials = LinkedInCredentials.load(Path(".env"))
    except ConfigurationError as exc:
        print("configuration_error={}".format(exc), file=sys.stderr)
        return 2

    request = build_request(args.vanity, credentials)
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = response.read(2_000_001)
            status = response.status
            content_type = response.headers.get_content_type()
    except urllib.error.HTTPError as exc:
        print("status={}".format(exc.code))
        print("result=http_error")
        return 1
    except urllib.error.URLError:
        print("result=network_error")
        return 1

    print("status={}".format(status))
    print("content_type={}".format(content_type))
    print("response_bytes={}".format(len(body)))
    if len(body) > 2_000_000:
        print("result=response_too_large")
        return 1

    try:
        stream = FlightStream.parse(body)
    except FlightDecodeError:
        print("result=non_flight_response")
        return 1

    print("flight_records={}".format(stream.record_count))
    print("flight_imports={}".format(stream.import_count))
    print("flight_data_records={}".format(stream.data_count))
    print("top_card_anchors={}".format(len(list(stream.find_objects(
        "observabilityIdentifier",
        "com.linkedin.sdui.impl.profile.components.topCard",
    )))))
    print("result=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
