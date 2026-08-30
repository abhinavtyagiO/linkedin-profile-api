"""Stable error taxonomy shared by the client and HTTP API."""

from __future__ import annotations


class ProfileApiError(Exception):
    code = "internal_error"
    http_status = 500
    retryable = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ServerConfigurationError(ProfileApiError):
    code = "server_configuration_error"
    http_status = 500


class InvalidProfileUrl(ProfileApiError):
    code = "invalid_profile_url"
    http_status = 422


class LinkedInAuthenticationError(ProfileApiError):
    code = "linkedin_authentication_failed"
    http_status = 503


class LinkedInProfileNotFound(ProfileApiError):
    code = "profile_not_found"
    http_status = 404


class LinkedInRateLimited(ProfileApiError):
    code = "linkedin_rate_limited"
    http_status = 503
    retryable = True


class LinkedInChallenge(ProfileApiError):
    code = "linkedin_challenge_required"
    http_status = 503


class LinkedInProtocolError(ProfileApiError):
    code = "linkedin_protocol_changed"
    http_status = 502


class LinkedInUnavailable(ProfileApiError):
    code = "linkedin_unavailable"
    http_status = 502
    retryable = True
