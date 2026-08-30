"""Public response schema for normalized LinkedIn profiles."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FetchProfileRequest(BaseModel):
    profile_url: str = Field(
        ...,
        examples=["https://www.linkedin.com/in/example-person/"],
    )


class ProfileImages(BaseModel):
    profile: Optional[str] = None
    background: Optional[str] = None


class Experience(BaseModel):
    title: str
    company: Optional[str] = None
    employment_type: Optional[str] = None
    date_range: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    company_logo_url: Optional[str] = None


class Education(BaseModel):
    school: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    date_range: Optional[str] = None
    description: Optional[str] = None
    school_logo_url: Optional[str] = None


class Skill(BaseModel):
    name: str
    evidence: List[str] = Field(default_factory=list)


class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None


class Language(BaseModel):
    name: str
    proficiency: Optional[str] = None


class ResponseMetadata(BaseModel):
    source: str = "linkedin_flagship_web"
    fetched_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completeness: Dict[str, str] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    profile_url: str
    vanity_name: str
    name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    images: ProfileImages = Field(default_factory=ProfileImages)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
