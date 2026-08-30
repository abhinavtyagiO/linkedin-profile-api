"""Allowlisted extraction from resolved LinkedIn React/SDUI trees."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from .errors import LinkedInProtocolError
from .flight import FlightStream, REACT_ELEMENT
from .models import (
    Certification,
    Education,
    Experience,
    Language,
    ProfileImages,
    ProfileResponse,
    ResponseMetadata,
    Skill,
)
from .protocol import PROFILE_COMPONENT_PREFIX, ProfileTarget


TOP_CARD_ID = "com.linkedin.sdui.impl.profile.components.topCard"
ABOUT_ID = "com.linkedin.sdui.impl.profile.components.aboutSection"
EXPERIENCE_ID = "com.linkedin.sdui.impl.profile.components.experienceTopLevelSection"
EDUCATION_ID = "com.linkedin.sdui.impl.profile.components.educationTopLevelSection"
CERTIFICATION_ID = "com.linkedin.sdui.impl.profile.components.certificationTopLevelSection"
LANGUAGE_ID = "com.linkedin.sdui.impl.profile.components.languageTopLevelSection"
SKILLS_ID = "com.linkedin.sdui.impl.profile.components.skillsSection"

_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DATE_RE = re.compile(
    r"^(?:(?:{})\s+\d{{4}}|\d{{4}})\s*[-–]".format(_MONTHS),
    re.IGNORECASE,
)
_EMPLOYMENT_TYPES = {
    "full-time",
    "part-time",
    "self-employed",
    "freelance",
    "contract",
    "internship",
    "apprenticeship",
    "seasonal",
}
_UI_PREFIXES = (
    "add ",
    "edit ",
    "show all",
    "view ",
    "open to work",
)


@dataclass(frozen=True)
class ImageCandidate:
    url: str
    width: int
    height: int
    shape: Optional[str]


def _root(stream: FlightStream) -> Any:
    try:
        return stream.resolve_record("0")
    except Exception as exc:
        raise LinkedInProtocolError("LinkedIn response did not contain a usable root") from exc


def _find_first(value: Any, field: str, expected: str) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        if value.get(field) == expected:
            return value
        for item in value.values():
            found = _find_first(item, field, expected)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first(item, field, expected)
            if found is not None:
                return found
    return None


def _flatten_text(value: Any) -> str:
    pieces: List[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, str):
            pieces.append(item)
            return
        if isinstance(item, list):
            if len(item) >= 4 and item[0] == REACT_ELEMENT:
                if item[1] == "br":
                    pieces.append("\n")
                    return
                props = item[3]
                if isinstance(props, dict):
                    visit(props.get("children"))
                return
            for child in item:
                visit(child)
            return
        if isinstance(item, dict) and "children" in item:
            visit(item["children"])

    visit(value)
    text = "".join(pieces)
    return "\n".join(part.strip() for part in text.splitlines() if part.strip()).strip()


def visible_text_blocks(value: Any) -> List[str]:
    """Return rendered text blocks while excluding actions and UI controls."""

    blocks: List[str] = []

    def visit(item: Any, direct_child: bool = False) -> None:
        if isinstance(item, str):
            text = item.strip()
            if direct_child and text:
                blocks.append(text)
            return
        if isinstance(item, list):
            if len(item) >= 4 and item[0] == REACT_ELEMENT:
                props = item[3]
                if isinstance(props, dict):
                    visit(props)
                return
            for child in item:
                visit(child, direct_child=direct_child)
            return
        if not isinstance(item, dict):
            return
        if "buttonProps" in item:
            return
        text_props = item.get("textProps")
        if isinstance(text_props, dict):
            text = _flatten_text(text_props.get("children"))
            if text:
                blocks.append(text)
            return
        skipped = {
            "action",
            "actions",
            "buttonProps",
            "displayedExpression",
            "modelStates",
            "onAppear",
            "onBackOverride",
            "onDisappear",
            "onReappear",
            "renderPayload",
            "style",
            "tracking",
            "triggers",
            "viewTrackingSpecs",
            "visibilityTriggers",
        }
        for key, child in item.items():
            if key in skipped or key.lower().startswith("tracking"):
                continue
            visit(child, direct_child=(key == "children"))

    visit(value)
    deduplicated: List[str] = []
    for block in blocks:
        if not deduplicated or deduplicated[-1] != block:
            deduplicated.append(block)
    return deduplicated


def _initial_items(section: Dict[str, Any]) -> List[Any]:
    groups: List[List[Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            items = value.get("initialItems")
            if isinstance(items, list):
                groups.append(items)
                return
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(section)
    if not groups:
        return []
    largest = max(groups, key=len)
    return [item.get("item", item) if isinstance(item, dict) else item for item in largest]


def _image_candidates(value: Any) -> List[ImageCandidate]:
    candidates: List[ImageCandidate] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            render = item.get("renderPayload")
            if isinstance(render, dict):
                root = render.get("rootUrl")
                renditions = render.get("imageRenditions")
                if isinstance(root, str) and isinstance(renditions, list):
                    for rendition in renditions:
                        if not isinstance(rendition, dict):
                            continue
                        suffix = rendition.get("suffixUrl")
                        if not isinstance(suffix, str):
                            continue
                        url = root + suffix
                        hostname = (urlparse(url).hostname or "").lower()
                        if hostname == "media.licdn.com" or hostname.endswith(".licdn.com"):
                            candidates.append(
                                ImageCandidate(
                                    url=url,
                                    width=int(rendition.get("width") or 0),
                                    height=int(rendition.get("height") or 0),
                                    shape=item.get("shape"),
                                )
                            )
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return candidates


def _largest_image(value: Any, shape: Optional[str] = None) -> Optional[str]:
    candidates = _image_candidates(value)
    if shape is not None:
        candidates = [candidate for candidate in candidates if candidate.shape == shape]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.width * item.height).url


def extract_top_card(stream: FlightStream) -> Tuple[str, Optional[str], Optional[str], ProfileImages]:
    section = _find_first(_root(stream), "observabilityIdentifier", TOP_CARD_ID)
    if section is None:
        raise LinkedInProtocolError("LinkedIn top card was not found")
    blocks = visible_text_blocks(section)
    if not blocks:
        raise LinkedInProtocolError("LinkedIn top card contained no visible identity")

    name = blocks[0]
    meaningful = [
        item
        for item in blocks[1:]
        if item != "·"
        and not item.lower().startswith("view ")
        and "verification" not in item.lower()
    ]
    headline = meaningful[0] if meaningful else None

    location: Optional[str] = None
    try:
        contact_index = blocks.index("Contact info")
    except ValueError:
        contact_index = -1
    if contact_index > 0:
        for item in reversed(blocks[:contact_index]):
            if item != "·" and item != name and item != headline:
                if "verification" not in item.lower() and not item.lower().startswith("view "):
                    location = item
                    break

    profile_image = _largest_image(section, shape="circle")
    background_candidates = [
        item
        for item in _image_candidates(section)
        if item.width > 0 and item.height > 0 and item.width / item.height >= 2.5
    ]
    background = (
        max(background_candidates, key=lambda item: item.width * item.height).url
        if background_candidates
        else None
    )
    return name, headline, location, ProfileImages(
        profile=profile_image,
        background=background,
    )


def extract_about(stream: Optional[FlightStream]) -> Optional[str]:
    if stream is None:
        return None
    section = _find_first(_root(stream), "observabilityIdentifier", ABOUT_ID)
    if section is None:
        return None
    candidates = [
        item
        for item in visible_text_blocks(section)
        if item.lower() != "about"
        and not item.lower().startswith(_UI_PREFIXES)
        and len(item) > 1
    ]
    return max(candidates, key=len) if candidates else None


def _clean_item_lines(item: Any, section_title: str) -> List[str]:
    lines: List[str] = []
    for block in visible_text_blocks(item):
        text = block.strip()
        lowered = text.lower()
        if not text or lowered == section_title.lower():
            continue
        if lowered.startswith(_UI_PREFIXES):
            continue
        if text not in lines:
            lines.append(text)
    return lines


def _split_date(value: str) -> Tuple[str, Optional[str]]:
    pieces = [piece.strip() for piece in value.split(" · ", 1)]
    return pieces[0], pieces[1] if len(pieces) > 1 else None


def _is_date(value: str) -> bool:
    return bool(_DATE_RE.match(value))


def _is_location(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"hybrid", "remote", "on-site", "onsite"}:
        return True
    if any(marker in lowered for marker in (" · hybrid", " · remote", " · on-site")):
        return True
    return "," in value and len(value) < 100 and not value.endswith((".", "!", "?"))


def _split_company_meta(value: str) -> Tuple[str, Optional[str]]:
    pieces = [piece.strip() for piece in value.split(" · ")]
    if len(pieces) > 1 and pieces[-1].lower() in _EMPLOYMENT_TYPES:
        return " · ".join(pieces[:-1]), pieces[-1]
    return value, None


def extract_experience(stream: Optional[FlightStream]) -> List[Experience]:
    if stream is None:
        return []
    section = _find_first(_root(stream), "observabilityIdentifier", EXPERIENCE_ID)
    if section is None:
        return []
    result: List[Experience] = []
    for item in _initial_items(section):
        lines = _clean_item_lines(item, "Experience")
        date_indexes = [index for index, line in enumerate(lines) if _is_date(line)]
        if not date_indexes:
            continue
        logo = _largest_image(item)
        first_date = date_indexes[0]
        grouped = first_date >= 3
        if grouped:
            company = lines[0]
            company_meta = lines[1]
            employment_type = company_meta.split(" · ", 1)[0] if company_meta else None
            group_location = lines[2] if first_date > 3 and _is_location(lines[2]) else None
        else:
            company_meta = lines[1] if len(lines) > 1 else ""
            company, employment_type = _split_company_meta(company_meta)
            group_location = None

        for position, date_index in enumerate(date_indexes):
            if date_index == 0:
                continue
            # Standalone entries are rendered as title, company, date. Grouped
            # entries are rendered as company summary followed by title, date
            # pairs. The previous shared date-1 rule therefore returned the
            # company name as the title for standalone jobs.
            title = lines[date_index - 1] if grouped else lines[0]
            date_range, duration = _split_date(lines[date_index])
            next_date = date_indexes[position + 1] if position + 1 < len(date_indexes) else len(lines)
            segment_end = next_date - 1 if next_date < len(lines) else next_date
            trailing = lines[date_index + 1 : segment_end]
            location = group_location
            if trailing and _is_location(trailing[0]):
                location = trailing.pop(0)
            description_lines = [
                line
                for line in trailing
                if "skills" not in line.lower() and "endorsement" not in line.lower()
            ]
            result.append(
                Experience(
                    title=title,
                    company=company,
                    employment_type=employment_type,
                    date_range=date_range,
                    duration=duration,
                    location=location,
                    description="\n".join(description_lines) or None,
                    company_logo_url=logo,
                )
            )
    return result


def extract_education(stream: Optional[FlightStream]) -> List[Education]:
    if stream is None:
        return []
    section = _find_first(_root(stream), "observabilityIdentifier", EDUCATION_ID)
    if section is None:
        return []
    result: List[Education] = []
    for item in _initial_items(section):
        lines = _clean_item_lines(item, "Education")
        if not lines:
            continue
        date_index = next((index for index, value in enumerate(lines) if _is_date(value)), None)
        date_range = lines[date_index] if date_index is not None else None
        before_date = lines[:date_index] if date_index is not None else lines
        description = lines[date_index + 1 :] if date_index is not None else []
        result.append(
            Education(
                school=before_date[0],
                degree=before_date[1] if len(before_date) > 1 else None,
                field_of_study=before_date[2] if len(before_date) > 2 else None,
                date_range=date_range,
                description="\n".join(description) or None,
                school_logo_url=_largest_image(item),
            )
        )
    return result


def extract_skills(stream: Optional[FlightStream]) -> List[Skill]:
    if stream is None:
        return []
    section = _find_first(_root(stream), "observabilityIdentifier", SKILLS_ID)
    if section is None:
        return []
    result: List[Skill] = []
    for item in _initial_items(section):
        lines = _clean_item_lines(item, "Skills")
        if lines:
            result.append(Skill(name=lines[0], evidence=lines[1:]))
    return result


def extract_skills_page(stream: FlightStream) -> List[Skill]:
    """Extract one server-rendered page of skill collection items."""

    root = _root(stream)
    item_nodes: Dict[str, Dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            component_key = value.get("componentkey") or value.get("componentKey")
            if (
                isinstance(component_key, str)
                and component_key.startswith("entity-collection-item-")
                and component_key not in item_nodes
            ):
                item_nodes[component_key] = value
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(root)
    skills: List[Skill] = []
    for item in item_nodes.values():
        lines = _clean_item_lines(item, "Skills")
        if lines:
            skills.append(Skill(name=lines[0], evidence=lines[1:]))
    return skills


def extract_certifications(stream: Optional[FlightStream]) -> List[Certification]:
    if stream is None:
        return []
    section = _find_first(_root(stream), "observabilityIdentifier", CERTIFICATION_ID)
    if section is None:
        return []
    result: List[Certification] = []
    for item in _initial_items(section):
        lines = _clean_item_lines(item, "Licenses & certifications")
        if not lines:
            continue
        issue = next((line for line in lines if line.lower().startswith("issued ")), None)
        credential = next(
            (line for line in lines if line.lower().startswith("credential id")),
            None,
        )
        result.append(
            Certification(
                name=lines[0],
                issuer=lines[1] if len(lines) > 1 and lines[1] not in {issue, credential} else None,
                issue_date=issue,
                credential_id=credential,
            )
        )
    return result


def extract_languages(stream: Optional[FlightStream]) -> List[Language]:
    if stream is None:
        return []
    section = _find_first(_root(stream), "observabilityIdentifier", LANGUAGE_ID)
    if section is None:
        return []
    result: List[Language] = []
    for item in _initial_items(section):
        lines = _clean_item_lines(item, "Languages")
        if lines:
            result.append(Language(name=lines[0], proficiency=lines[1] if len(lines) > 1 else None))
    return result


def extract_profile(
    target: ProfileTarget,
    base_stream: FlightStream,
    components: Dict[str, FlightStream],
    skill_pages: Sequence[FlightStream] = (),
) -> ProfileResponse:
    def component(suffix: str) -> Optional[FlightStream]:
        return components.get(PROFILE_COMPONENT_PREFIX + suffix)

    name, headline, location, images = extract_top_card(base_stream)
    about_stream = component("profileCardsAboveActivity")
    experience_stream = component("profileCardsExperienceOnly")
    part1 = component("profileCardsBelowActivityPart1WithoutExp")
    part4 = component("profileCardsBelowActivityPart4")
    part7 = component("profileCardsBelowActivityPart7")

    about = extract_about(about_stream)
    experience = extract_experience(experience_stream)
    education = extract_education(part1)
    certifications = extract_certifications(part1)
    languages = extract_languages(part4)
    paged_skills: List[Skill] = []
    for page in skill_pages:
        paged_skills.extend(extract_skills_page(page))
    skills = paged_skills or extract_skills(part7)
    if skills:
        deduplicated_skills: List[Skill] = []
        seen_skill_names = set()
        for skill in skills:
            normalized = skill.name.casefold()
            if normalized in seen_skill_names:
                continue
            seen_skill_names.add(normalized)
            deduplicated_skills.append(skill)
        skills = deduplicated_skills

    status = {
        "top_card": "complete" if headline and location else "partial",
        "about": "present" if about else "empty_or_not_public",
        "experience": "present" if experience else "empty_or_not_public",
        "education": "present" if education else "empty_or_not_public",
        "skills": "present" if skills else "empty_or_not_public",
        "certifications": "present" if certifications else "empty_or_not_public",
        "languages": "present" if languages else "empty_or_not_public",
    }
    missing = [
        suffix
        for suffix in (
            "profileCardsAboveActivity",
            "profileCardsExperienceOnly",
            "profileCardsBelowActivityPart1WithoutExp",
            "profileCardsBelowActivityPart4",
            "profileCardsBelowActivityPart7",
        )
        if component(suffix) is None
    ]
    warnings = (
        ["LinkedIn did not advertise components: {}".format(", ".join(missing))]
        if missing
        else []
    )
    if experience_stream is not None and not experience:
        experience_section = _find_first(
            _root(experience_stream),
            "observabilityIdentifier",
            EXPERIENCE_ID,
        )
        if experience_section is not None and _initial_items(experience_section):
            warnings.append(
                "LinkedIn returned Experience entries, but none could be parsed"
            )
    return ProfileResponse(
        profile_url=target.canonical_url,
        vanity_name=target.vanity_name,
        name=name,
        headline=headline,
        location=location,
        about=about,
        images=images,
        experience=experience,
        education=education,
        skills=skills,
        certifications=certifications,
        languages=languages,
        metadata=ResponseMetadata(completeness=status, warnings=warnings),
    )
