"""Configuration loading with deliberately secret-free errors and reprs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional


class ConfigurationError(ValueError):
    """Raised when required configuration is absent or malformed."""


def read_dotenv(path: Path) -> Dict[str, str]:
    """Read a small, non-interpolating dotenv file.

    The parser supports the subset needed by this project: comments, blank
    lines, optional ``export``, and single- or double-quoted values. It never
    mutates ``os.environ`` and never includes values in exceptions.
    """

    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigurationError(
                "Invalid environment entry on line {}".format(line_number)
            )

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "A").isalnum():
            raise ConfigurationError(
                "Invalid environment key on line {}".format(line_number)
            )

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value

    return values


@dataclass(frozen=True, repr=False)
class LinkedInCredentials:
    li_at: str
    jsessionid: str

    def __repr__(self) -> str:
        return "LinkedInCredentials(li_at=<redacted>, jsessionid=<redacted>)"

    @property
    def csrf_token(self) -> str:
        return self.jsessionid.strip('"')

    @property
    def cookie_header(self) -> str:
        jsessionid = self.jsessionid
        if not (jsessionid.startswith('"') and jsessionid.endswith('"')):
            jsessionid = '"{}"'.format(jsessionid)
        return "li_at={}; JSESSIONID={}; lang=v=2&lang=en-us".format(
            self.li_at,
            jsessionid,
        )

    @classmethod
    def load(
        cls,
        dotenv_path: Path = Path(".env"),
        environ: Optional[Mapping[str, str]] = None,
    ) -> "LinkedInCredentials":
        file_values = read_dotenv(dotenv_path)
        environment = os.environ if environ is None else environ

        li_at = environment.get("LINKEDIN_LI_AT") or file_values.get(
            "LINKEDIN_LI_AT", ""
        )
        jsessionid = environment.get("LINKEDIN_JSESSIONID") or file_values.get(
            "LINKEDIN_JSESSIONID", ""
        )

        missing = []
        if not li_at:
            missing.append("LINKEDIN_LI_AT")
        if not jsessionid:
            missing.append("LINKEDIN_JSESSIONID")
        if missing:
            raise ConfigurationError(
                "Missing required environment variable(s): {}".format(
                    ", ".join(missing)
                )
            )

        return cls(li_at=li_at, jsessionid=jsessionid)
