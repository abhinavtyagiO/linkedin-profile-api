# Design and Research Plan

This was the implementation plan agreed before coding. Checkpoint statuses document what was subsequently completed.

## 1. Reverse-engineering methodology

1. Use a browser manually with an operator-owned account and profile.
2. Inventory requests during one isolated UI action at a time.
3. Save only sanitized method/path/query-key/body-shape observations in tracked documentation.
4. Keep raw cURL/HAR/response material private and untracked.
5. Replay one captured request outside the browser with credentials from environment variables.
6. Remove captured browser metadata systematically and compare status, content type, response size, Flight record counts, and semantic anchors.
7. Read typed actions embedded in the response to discover the next request instead of hardcoding request-scoped values.
8. Verify uncertain serialization behavior against LinkedIn's first-party JavaScript loaded by that page.

Checkpoint: complete for the base profile, profile components, Skills detail, and Skills pagination.

## 2. Experiment log structure

Every experiment records:

- ID and timestamp
- research question and hypothesis
- test-account/profile class without personal values
- exact controlled variable
- sanitized request/response structure
- pass/fail/inconclusive result
- confidence and next experiment
- explicit redaction check

Checkpoint: implemented in `docs/experiment-log.md`.

## 3. Architecture

The runtime is split into six boundaries:

```text
public HTTP API
  -> orchestration service
  -> direct LinkedIn HTTP client
  -> bounded Flight decoder
  -> protocol/action discovery
  -> allowlisted section normalizers
```

The browser is absent from every production boundary. Raw upstream trees never cross the public API boundary.

Checkpoint: implemented.

## 4. API schema

Input is one `profile_url`. Output uses stable objects for identity, images, experience, education, skills, certifications, languages, and completeness metadata. Null and empty values are explicit. Errors use `code`, `message`, and `retryable` rather than leaking upstream bodies.

Checkpoint: implemented at `POST /v1/profiles:fetch`, with OpenAPI at `/docs`.

## 5. Repository layout

```text
src/linkedin_profile_api/
  app.py          public FastAPI surface
  client.py       authenticated direct transport
  config.py       secret-safe environment loading
  errors.py       stable failure taxonomy
  extract.py      allowlisted normalization
  flight.py       bounded Flight decoder
  models.py       public schema
  protocol.py     request builders/action discovery
  service.py      request graph and pagination
scripts/          secret-safe research probes
tests/            offline tests and synthetic fixtures
docs/             research, protocol, and capture notes
```

Checkpoint: implemented.

## 6. Testing strategy

- Unit-test URL validation and request/action discovery.
- Unit-test every observed Flight token with synthetic data.
- Enforce malformed-input and resource-limit failures.
- Unit-test section extraction with synthetic React/SDUI trees.
- Contract-test health, success, and stable error responses using an injected fake service.
- Run a metadata-only live smoke test against the operator-owned profile.
- Never commit live profile responses.

Checkpoint: 19 offline tests plus a successful live end-to-end smoke test.

## 7. Deployment plan

- Build a minimal non-root container.
- Run a single worker for one LinkedIn session.
- Inject `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` through the hosting platform's secret store.
- Publish behind provider-managed HTTPS.
- Use `/health` for platform health checks.
- Keep concurrency conservative and do not retry authentication/challenge failures.

Checkpoint: Dockerfile and Render Blueprint are ready. Creating the public service requires access to the candidate's chosen hosting account and secret entry in its dashboard.

## 8. Known risks and limitations

- Undocumented protocols can change abruptly.
- Session credentials expire and can trigger challenge pages.
- Automated access may be restricted by LinkedIn policy or rate limits.
- Profile visibility changes by viewer and privacy settings.
- Current structural validation uses one operator-owned profile; non-self variations need an authorized second fixture.
- Rendered SDUI text requires heuristics for some experience groupings.
- Pagination is deliberately capped.
- No challenge solving, credential rotation, or browser fallback exists.

Checkpoint: documented and reflected in stable error/completeness behavior.
