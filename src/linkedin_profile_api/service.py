"""Application service that orchestrates the direct LinkedIn request graph."""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from .client import LinkedInClient
from .config import LinkedInCredentials
from .errors import LinkedInProfileNotFound
from .extract import extract_profile
from .flight import FlightStream
from .models import ProfileResponse
from .protocol import (
    PROFILE_COMPONENT_PREFIX,
    discover_detail_action,
    discover_pagination_request,
    discover_profile_components,
    is_profile_not_found,
    parse_profile_url,
)


SKILLS_PAGER_ID = "com.linkedin.sdui.pagers.profile.details.skills"
SKILLS_ALL_FILTER = "ProfileSkillCategory_ALL"
SKILLS_PAGE_SIZE = 50


class ProfileService:
    def __init__(
        self,
        client: LinkedInClient,
        max_skill_pages: int = 10,
        max_component_workers: int = 3,
    ) -> None:
        self.client = client
        self.max_skill_pages = max_skill_pages
        self.max_component_workers = max(1, max_component_workers)

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "ProfileService":
        credentials = LinkedInCredentials.load(env_file or Path(".env"))
        return cls(LinkedInClient(credentials))

    def fetch(self, profile_url: str) -> ProfileResponse:
        target = parse_profile_url(profile_url)
        base_stream = self.client.fetch_base_profile(target.vanity_name)
        if is_profile_not_found(base_stream):
            raise LinkedInProfileNotFound("LinkedIn profile was not found")
        component_ids = discover_profile_components(base_stream)
        components = self._fetch_components(target.vanity_name, component_ids)

        skill_pages: List[FlightStream] = []
        skills_component = components.get(
            PROFILE_COMPONENT_PREFIX + "profileCardsBelowActivityPart7"
        )
        if skills_component is not None:
            detail_action = discover_detail_action(skills_component, "skills")
            if detail_action is not None:
                detail_stream = self.client.fetch_detail(
                    target.vanity_name,
                    detail_action,
                )
                next_page = discover_pagination_request(
                    detail_stream,
                    SKILLS_PAGER_ID,
                    SKILLS_ALL_FILTER,
                )
                for _ in range(self.max_skill_pages):
                    if next_page is None:
                        break
                    next_page = _with_minimum_page_size(
                        next_page,
                        SKILLS_PAGE_SIZE,
                    )
                    page = self.client.fetch_pagination(
                        target.vanity_name,
                        detail_action["screenId"],
                        next_page,
                    )
                    skill_pages.append(page)
                    next_page = discover_pagination_request(
                        page,
                        SKILLS_PAGER_ID,
                        SKILLS_ALL_FILTER,
                    )

        return extract_profile(
            target,
            base_stream,
            components,
            skill_pages=skill_pages,
        )

    def _fetch_components(
        self,
        vanity_name: str,
        component_ids: List[str],
    ) -> Dict[str, FlightStream]:
        if not component_ids:
            return {}
        worker_count = min(self.max_component_workers, len(component_ids))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                component_id: executor.submit(
                    self.client.fetch_component,
                    vanity_name,
                    component_id,
                )
                for component_id in component_ids
            }
            return {
                component_id: futures[component_id].result()
                for component_id in component_ids
            }


def _with_minimum_page_size(
    pagination_request: Dict[str, Any],
    page_size: int,
) -> Dict[str, Any]:
    normalized = copy.deepcopy(pagination_request)
    payload = normalized.get("requestedArguments", {}).get("payload")
    if isinstance(payload, dict):
        current_count = payload.get("count")
        if not isinstance(current_count, int) or current_count < page_size:
            payload["count"] = page_size
    return normalized
