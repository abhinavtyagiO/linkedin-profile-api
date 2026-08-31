# Reverse-Engineering Experiment Summary

This is a condensed record of the experiments that shaped the implementation.
It intentionally excludes credentials, raw LinkedIn responses, personal
profile values, and request-specific metadata.

## 1. Identify the profile data requests

**Question:** What does LinkedIn request when an authenticated profile opens?

**Finding:** The current website loads profile data from the `/flagship-web/`
area. The main profile and individual profile sections are separate requests.

**Decision:** Use the current Flagship request flow rather than assuming the
older Voyager API described by existing scraper projects.

## 2. Reproduce the main request directly

**Question:** Does the profile request require a running browser?

**Finding:** The request succeeded from a standalone Python HTTP client using
session values supplied through the environment.

**Decision:** Keep the browser as a manual research tool only. Use a direct
HTTP client in production.

## 3. Minimize the request

**Question:** Which captured browser headers are actually required?

**Finding:** Tracking, tracing, browser-hint, and page-instance metadata could
be removed. Authentication, request content, origin context, and the response
format indicator were sufficient for the tested flow.

**Decision:** Send a small, understandable request rather than replaying a full
browser capture.

## 4. Decode the response

**Question:** Why could the response not be parsed as ordinary JSON?

**Finding:** LinkedIn returns React Flight records with references between
records. Some text records are length-framed and may contain newlines.

**Decision:** Build a bounded Flight decoder with byte, record, depth, cycle,
and reference limits. Use only synthetic fixtures in the repository.

## 5. Discover profile sections

**Question:** How should the client find About, experience, education,
languages, and Skills?

**Finding:** The main response advertises actions for loading additional
profile components. The Skills view also advertises its continuation actions.

**Decision:** Follow typed actions returned by LinkedIn and allowlist only the
sections needed by the assignment. Do not hardcode temporary capture values.

## 6. Normalize the public response

**Question:** How should UI-oriented data become stable profile JSON?

**Finding:** Relevant profile values are mixed with editing controls,
analytics, recommendations, promotions, and tracking data. Layouts may also
vary between profiles.

**Decision:** Extract only assignment fields, support the observed layout
variants, and omit null or empty values from the response.

## 7. Classify errors correctly

**Question:** How should upstream failures map to the public API?

**Finding:** Authentication, verification, rate limiting, and malformed
responses have different meanings. LinkedIn can also represent a missing
profile inside a successful HTTP response.

**Decision:** Return stable error codes and detect LinkedIn's semantic missing
profile screen instead of relying on status codes or localized error text.

## 8. Handle language and parser variations

**Question:** Why did a valid profile sometimes lose its experience data or
fail decoding?

**Finding:** Rendered labels can change with language, experience cards have
more than one layout, and long About text can use length-framed Flight records.

**Decision:** Request a consistent language, support both observed experience
layouts, warn when visible data cannot be extracted, and parse length-framed
text by byte count.

## 9. Reduce latency

**Question:** Which requests can safely overlap?

**Finding:** Profile components are independent after the main response, while
detail navigation and pagination remain dependent. Skills can also request a
larger page size.

**Decision:** Fetch independent components with a small concurrency limit and
request up to 50 Skills per page. Do not cache profile responses.

## 10. Verify the release

The final checks covered the offline test suite, container startup, health and
OpenAPI routes, secret-file exclusions, public response shape, and a
metadata-only live request. No real profile response was committed.

## Redaction policy

The repository contains structural findings only. It does not contain copied
cURL captures, HAR files, session values, raw LinkedIn bodies, internal member
identifiers, or private profile data.
