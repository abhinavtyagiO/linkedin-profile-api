"""Application service that orchestrates the direct LinkedIn request graph."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

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


class ProfileService:
    def __init__(self, client: LinkedInClient, max_skill_pages: int = 10) -> None:
        self.client = client
        self.max_skill_pages = max_skill_pages

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
        components: Dict[str, FlightStream] = {}
        for component_id in component_ids:
            components[component_id] = self.client.fetch_component(
                target.vanity_name,
                component_id,
            )

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
