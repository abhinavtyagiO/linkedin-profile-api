# Design and Research Plan

This is the plan I used before implementing the API. It focuses on the
decisions that matter to the assignment and leaves out capture-specific data.

## 1. Reverse-engineering method

1. Use my own LinkedIn account and a browser only for manual investigation.
2. Isolate one profile action at a time in DevTools.
3. Record sanitized request shapes and response behavior.
4. Replay the useful requests with a standalone HTTP client.
5. Remove unnecessary browser headers through controlled experiments.
6. Discover follow-up actions from LinkedIn's response instead of copying
   temporary request identifiers.

The production application never starts or controls a browser.

## 2. Experiment records

For each useful experiment I recorded the question, sanitized observation,
conclusion, and resulting implementation decision. I did not retain cookies,
raw responses, personal profile data, or request-specific identifiers.

## 3. Architecture

```text
FastAPI route
  -> profile service
  -> direct LinkedIn HTTP client
  -> React Flight decoder
  -> section discovery and extraction
  -> public response model
```

Each layer has one job. The public API never exposes LinkedIn's raw response.

## 4. API schema

The API accepts one LinkedIn profile URL. A successful response contains the
available identity, image, experience, education, skill, certification, and
language fields. Fields LinkedIn does not return are omitted.

Expected failures use a stable structure:

```json
{
  "code": "profile_not_found",
  "message": "The LinkedIn profile was not found",
  "retryable": false
}
```

## 5. Repository layout

```text
src/linkedin_profile_api/  application and LinkedIn protocol code
tests/                     offline tests and synthetic fixtures
scripts/                   metadata-only diagnostic tools
docs/                      summarized design and research notes
```

## 6. Testing strategy

- Test URL validation and public error responses.
- Test Flight record parsing, references, and safety limits.
- Test section extraction with synthetic data.
- Test component discovery and Skills pagination.
- Test missing-profile detection and changed-protocol handling.
- Keep live profile responses and credentials out of fixtures.

The current offline suite contains 33 tests.

## 7. Deployment plan

- Package the API in a non-root container.
- Store LinkedIn session values in the hosting provider's secret environment.
- Use one application worker and conservative upstream concurrency.
- Expose `/health` for platform checks and `/docs` for API documentation.
- Deploy behind provider-managed HTTPS.

The current deployment runs on Railway.

## 8. Risks and limitations

- LinkedIn's internal endpoints can change without notice.
- Session credentials expire and may trigger verification.
- Visibility depends on the authenticated LinkedIn account.
- LinkedIn may rate-limit automated requests.
- Rendered profile layouts and languages can vary.
- The API does not solve challenges, rotate accounts, or fall back to a
  browser.

These cases are returned as explicit API errors or documented response
warnings rather than being hidden.
