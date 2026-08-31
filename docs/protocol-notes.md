# LinkedIn Protocol Notes

These notes summarize the protocol behavior the application depends on. They
are intentionally limited to stable, implementation-relevant findings rather
than reproducing browser captures.

## Scope

The observed LinkedIn web application loads profiles through undocumented
`/flagship-web/` endpoints. This implementation uses those endpoints directly
with an authenticated HTTP session. It does not use LinkedIn's official API and
does not run a browser.

## Request flow

```text
profile URL
  -> main Flagship profile request
  -> discover advertised profile components
  -> fetch assignment-relevant components
  -> open the Skills detail view when available
  -> follow Skills continuations within a fixed limit
```

The main profile route provides the top card and actions for loading other
sections. Component actions provide About, experience, education,
certifications, languages, and Skills. Recommendation and activity components
are ignored because they are outside the assignment.

Follow-up requests are built from actions in the current response. Temporary
values copied from DevTools are never stored or hardcoded.

## Authentication and request minimization

The client reads two LinkedIn session values from environment variables and
builds the corresponding authenticated request. Secrets are never accepted in
the public API payload or printed in logs.

Controlled replay showed that browser tracking, tracing, client hints, and
page-instance metadata were not needed. The client keeps only the headers and
body fields required for authentication, request context, and the Flight
response format. It also requests a consistent language because some profile
fields are rendered text.

## Response format

LinkedIn returns React Flight data rather than a single JSON object. The
decoder performs three steps:

1. Read each record while respecting line-delimited and length-framed forms.
2. Build a record table and resolve references safely.
3. Traverse only the relevant component trees.

The decoder limits response bytes, record sizes and counts, nesting depth,
reference resolution, and cycles. A response outside those limits is rejected
as a protocol error.

## Extraction rules

The raw component trees mix profile information with UI state, editing tools,
analytics, tracking, and promotional content. The extractor uses an allowlist
and returns only the fields defined by the public API.

Some profile sections have more than one observed layout. The extractor
supports those known variants and warns when a visible section cannot be
interpreted. Missing and empty values are omitted from successful responses.

## Skills pagination

The Skills component links to a separate detail view. That view supplies the
continuation action for the next page. The client follows those actions until
there is no continuation or a safety limit is reached. It requests up to 50
items per page to reduce latency.

## Error classification

The service distinguishes:

- invalid profile URLs;
- missing profiles;
- expired authentication;
- login or verification challenges;
- rate limiting;
- network or upstream availability failures;
- responses that no longer match the understood protocol.

LinkedIn may return HTTP 200 for a missing profile. The service recognizes the
semantic missing-profile screen and maps it to `404 profile_not_found` rather
than depending on localized visible text.

## Privacy and redaction

Only sanitized structural findings are committed. The repository excludes raw
profile responses, copied cURL requests, HAR files, cookies, request-specific
identifiers, and personal profile fixtures. Tests use synthetic data.

## Known limitations

- The endpoints are undocumented and may change.
- Returned data depends on the authenticated account's visibility.
- Sessions expire and LinkedIn may require verification.
- New profile layouts may require extractor updates.
- The client does not solve challenges or fall back to browser automation.
