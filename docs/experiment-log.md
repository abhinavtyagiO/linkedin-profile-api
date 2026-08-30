# Reverse-Engineering Experiment Log

This tracked log contains sanitized structural findings only. Never add cookies, CSRF values, copied cURL commands, HAR files, raw responses, internal member identifiers, or personal profile values.

## EXP-20260830-001 - Main profile request inventory

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Test-account class: operator-owned, authenticated
- Test-profile class: operator's own profile
- Status: pass
- Research question: Which LinkedIn-owned resources are requested while an authenticated profile page loads?
- Method: Opened the profile manually in the Codex in-app browser and inspected the browser's observed page-resource inventory. No cookies or storage were inspected.
- Result:
  - The profile loaded successfully while authenticated.
  - No `/voyager/api/` or `/voyager/api/graphql` resource was observed in this page build.
  - Profile data traffic used the `/flagship-web/` namespace and React/server-driven UI action routes.
  - A profile route shaped as `/flagship-web/in/<vanity>/` was observed.
  - Repeated component requests used `/flagship-web/rsc-action/actions/component` with query keys `componentId`, `sduiid`, and `parentSpanId`.
  - Other observed action routes included `server-request` and `app-config`.
- Confidence: high for observed paths and query-key names; unknown for HTTP methods, headers, and response bodies because this browser surface does not expose them.
- Follow-up: capture one relevant request in desktop DevTools, redact secrets, and replay it outside the browser.

## EXP-20260830-002 - Main profile component names

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Do profile component requests carry stable, descriptive component identifiers?
- Result: The following non-secret component IDs were observed:

```text
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsActivity
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart1WithoutExp
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart2
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart3
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart4
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart5
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart6
com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart7
com.linkedin.sdui.generated.profile.dsl.impl.browsemapRecommendedEntitySection
com.linkedin.sdui.generated.profile.dsl.impl.pymkRecommendedEntitySection
com.linkedin.sdui.generated.profile.dsl.impl.productRecommendedEntitySection
```

- Interpretation: LinkedIn's current profile UI is assembled from server-driven components. The `profileCards...` requests are candidates for extracting profile sections; recommendation components are likely unrelated to the assignment output.
- Confidence: high that the identifiers were requested; low on the mapping from each numbered part to a public profile section until response bodies are inspected.
- Follow-up: correlate each component response with its rendered section using a DevTools response preview.

## EXP-20260830-003 - Skills detail navigation

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Which additional request shapes appear when opening the full Skills section?
- Result:
  - UI route: `/in/<vanity>/details/skills/`
  - Observed data route: `/flagship-web/in/<vanity>/details/skills/`
  - Additional action route: `/flagship-web/rsc-action/actions/pagination`
  - Pagination query keys: `sduiid`, `parentSpanId`
- Interpretation: the full Skills view has its own server-rendered data route and paginates through a generic action endpoint.
- Confidence: high for path/query-key observations; method, body, cursor representation, and response format remain unknown.
- Follow-up: capture the initial Skills route and one pagination request in DevTools.

## EXP-20260830-004 - Education detail navigation

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: inconclusive
- Research question: Which additional request shape appears when opening the full Education section?
- Result:
  - UI route: `/in/<vanity>/details/education/`
  - Observed data route: `/flagship-web/in/<vanity>/details/education/`
  - A component request named `com.linkedin.sdui.generated.profile.dsl.impl.profileCardsExperienceOnly` also appeared after the navigation.
- Interpretation: the education detail route is confirmed, but the `profileCardsExperienceOnly` request may be prefetch, shared layout data, or an unrelated concurrent component. It must not be labeled an education dependency yet.
- Confidence: high for the route; low for the component association.
- Follow-up: repeat with the network log cleared immediately before navigation and inspect initiator/response data.

## EXP-20260830-005 - Server-stream payload classification

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Is the observed `server-stream-request` obviously a profile-data request?
- Result:
  - Route: `/flagship-web/rsc-action/actions/server-stream-request`
  - Query keys: `sduiid`, `payload`, `_v`
  - The decoded `payload` was JSON with structural fields such as `requestId`, `serverRequest`, `requestedArguments`, `states`, `screenId`, `sessionId`, and `lastHeartbeatTimestamp`.
- Interpretation: this request looks like session/stream heartbeat infrastructure, not a primary profile-data candidate. It should be excluded from the first implementation until contrary evidence appears.
- Confidence: medium.
- Follow-up: verify its initiator and response type in DevTools; do not implement it preemptively.

## Redaction checklist

- [x] No authentication cookies or CSRF values
- [x] No copied cURL request or HAR data
- [x] No raw response body
- [x] No personal profile values or internal member identifier
- [x] No captured query-value identifiers such as `sduiid` or `parentSpanId`

## EXP-20260830-006 - First-party bundle request-helper inspection

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass with limited scope
- Research question: Do the first-party JavaScript bundles reveal LinkedIn's general authenticated request conventions?
- Method: Downloaded only the public `static.licdn.com` JavaScript bundles already referenced by the authenticated profile page. Files remain under the ignored private-research directory.
- Result: One bundle contains a generic XMLHttpRequest POST helper that:
  - sends a JSON body;
  - defaults `Content-Type` to `application/json`;
  - derives a `Csrf-Token` value from the `JSESSIONID` cookie;
  - enables credentialed requests;
  - accepts additional headers.
- Limitation: The minified bundle evidence does not prove that this helper sends the observed `/flagship-web/rsc-action/actions/component` request.
- Confidence: high for the helper behavior; low for its relevance to the profile endpoint.
- Follow-up: confirm the component request method, content type, CSRF header, and body in Chrome DevTools before using these conventions in code.

## EXP-20260830-007 - Captured Activity component request

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: What is the concrete request contract for one main-profile server-driven component?
- Capture: Chrome DevTools, operator-owned authenticated account and own profile.
- Endpoint:

```text
POST /flagship-web/rsc-action/actions/component
  ?componentId=com.linkedin.sdui.generated.profile.dsl.impl.profileCardsActivity
  &sduiid=<request-scoped-value>
  &parentSpanId=<request-scoped-value>
```

- Confirmed semantic request headers:
  - `Accept: */*`
  - `Content-Type: application/json`
  - `Csrf-Token: <derived/session-value>`
  - `Origin: https://www.linkedin.com`
  - `Referer: https://www.linkedin.com/in/<vanity>/`
  - `X-LI-Anchor-Page-Key: d_flagship3_profile_view_base`
  - `X-LI-Application-Instance: <build/session-value>`
  - `X-LI-Application-Version: <build-value>`
  - `X-LI-Page-Instance: <page-instance-value>`
  - `X-LI-Page-Instance-Tracking-Id: <page-instance-value>`
  - `X-LI-PageForestId: <trace-tree-value>`
  - `X-LI-RSC-Stream: true`
  - `X-LI-TraceParent: <trace-value>`
  - `X-LI-TraceState: <trace-value>`
  - `X-LI-Track: <client-metadata-json>`
  - authenticated Cookie header
- Browser-generated headers also present: language, priority, UA/client hints, and Fetch Metadata headers.
- Sanitized JSON body shape:

```json
{
  "clientArguments": {
    "payload": {
      "isSelfView": false,
      "vanityName": "<vanity>"
    },
    "states": [],
    "requestMetadata": {
      "$type": "proto.sdui.common.RequestMetadata"
    },
    "screenId": "com.linkedin.sdui.flagshipnav.home.Home",
    "knownTemplateIds": []
  }
}
```

- Security note: the original capture contained live authentication material and is intentionally not stored in the repository or research workspace. The exposed session must be revoked before replay experiments.
- Confidence: high.
- Follow-up: capture a fresh session through local environment variables and run header-minimization experiments without printing secret values.

## EXP-20260830-008 - Activity component response wire format

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: What response format does the Activity component return?
- Result:
  - The attached response was a data-URL-wrapped, base64-encoded payload.
  - Decoding produced 11,464 bytes of valid UTF-8.
  - The decoded body is a React Flight / React Server Component stream, not a single JSON document.
  - It contains 16 newline-delimited records: 9 `I` module-import records and 7 data records.
  - The dominant data record is a nested React element/model tree.
  - Parsed structural totals: 29 React element arrays, 135 objects, 63 arrays, 63 record/module references, and a maximum nesting depth of 39.
  - The stream contains typed SDUI models including navigation, click triggers, requested arguments, request metadata, and screen hierarchy.
  - Structural identifiers include the Activity section observability name and view names for recent activity and profile editing controls.
- Parsing implication: the adapter needs a React Flight record reader followed by SDUI/React-tree traversal. A Voyager-style `included[]` entity index will not parse this endpoint.
- Privacy note: no raw response or personal leaf value was copied into the repository.
- Confidence: high.
- Follow-up: create a fully synthetic Flight fixture with the same record/reference patterns before implementing the parser.

## EXP-20260830-009 - Above-Activity component request and response

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Which profile sections are represented by `profileCardsAboveActivity`, and how does its contract differ from Activity?
- Endpoint:

```text
POST /flagship-web/rsc-action/actions/component
  ?componentId=com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity
  &sduiid=<component-or-request-value>
  &parentSpanId=<request-scoped-value>
```

- Request differences from Activity:
  - `screenId` is `com.linkedin.sdui.flagshipnav.profile.Profile` rather than the Home screen.
  - `clientArguments.payload` includes `replaceableSectionArgs`.
  - It includes `profileComponentState` containing typed `BindingImpl` values in `MemoryNamespace` for refresh, cache, sticky-header, focus, featured-action, language-detail, and card-visibility state.
  - The body repeats the profile vanity identifier inside state-binding keys, so body-level redaction is required in shared captures.
- Response format:
  - 38,182 decoded UTF-8 bytes.
  - 48 Flight records: 10 module-import records and 38 data records.
  - Parsed tree: 125 React elements, 370 objects, 225 arrays, 285 references, and maximum depth 40.
  - Includes the `ReplaceableComponent` client export in addition to shared tracing, image, tracking, and trigger components.
- Observed section identifiers:

```text
com.linkedin.sdui.impl.profile.components.aboutSection
com.linkedin.sdui.impl.profile.components.analyticsSection
com.linkedin.sdui.impl.profile.components.featuredSection
com.linkedin.sdui.impl.profile.components.profileServicesSection
com.linkedin.sdui.impl.profile.components.salesInsightOrHighlightsSection
com.linkedin.sdui.impl.profile.components.suggestedForYouTopLevelSection
```

- Interpretation:
  - This component is a composite of upper-profile cards.
  - About and Featured may contribute assignment fields.
  - Analytics, Suggested for You, services, and sales/highlight cards are not part of the requested public profile schema and may be owner-only, promotional, or account-dependent.
  - The parser must allowlist domain fields and sections rather than recursively exposing all response content.
- Additional behavior: three embedded `ServerRequest` actions carry `coolOffToken` and `actionType` payloads, consistent with dynamic analytics or refresh behavior. They are not required for read-only profile extraction until proven otherwise.
- Confidence: high.
- Follow-up: identify the top-card/basic-identity source and capture `profileCardsBelowActivityPartN` components to map experience, education, skills, certifications, and languages.

## EXP-20260830-010 - Base profile navigation request and response

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Which direct endpoint returns the profile top card and basic identity screen?
- Endpoint and method:

```text
POST /flagship-web/in/<vanity>/
```

- Navigation context: client-side navigation from the Feed screen to the Profile screen.
- Request body type: `proto.sdui.actions.core.NavigateToScreen`.
- Important request-body structure:
  - target `screenId`: `com.linkedin.sdui.flagshipnav.profile.Profile`;
  - `pageKey`: `profile_view_base`;
  - full-page presentation;
  - target URL `/in/<vanity>/`;
  - hierarchy from Home to Profile;
  - `requestedArguments.payload.vanityName`;
  - `requestedArguments.payload.isVanityNameResolved`;
  - typed request metadata.
- Additional navigation headers compared with component requests:
  - `X-LI-Anchor-Page-Key` identifies the source screen;
  - `X-LI-Initial-URL` identifies the source route;
  - `X-LI-Layout-Tree` describes the source layout hierarchy;
  - `X-LI-RSC-Stream: true` requests the Flight stream.
- Response structure:
  - 362,508 UTF-8 bytes;
  - 253 newline-delimited Flight records;
  - 27 module-import records and 226 data records;
  - contains the profile top-card observability identifier, sticky-header component, supported-locales component, and profile-level navigation/actions;
  - contains a profile URN field and repeated vanity/self-view state;
  - includes view anchors such as `profile-top-card`, top-card photo, editing/overflow, verification, connections, contact/details, and public-profile actions.
- Top-card reference behavior:
  - the observable top-card wrapper points to other Flight records through lazy references;
  - the large resolved top-card subtree contains rendered text, URLs, image fields, actions, and UI/tracking models;
  - record IDs are capture-specific and must never be hardcoded.
- Extraction implication:
  - locate the top-card wrapper by semantic observability/view identifiers;
  - resolve Flight references;
  - extract an allowlisted set of visible text/image fields from the resolved subtree;
  - do not expect Voyager-style `firstName`, `lastName`, or `headline` object keys.
- Confidence: high.
- Follow-up: replay this request outside the browser and compare a second, non-self profile to identify stable top-card field positions.

## EXP-20260830-011 - Full document response

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Does the normal profile HTML document provide a cleaner basic-profile source than the Flagship navigation endpoint?
- Endpoint and method:

```text
GET /in/<vanity>/
```

- Result:
  - response size: approximately 916 KB;
  - standard HTML application shell with 18 script tags;
  - one inline script, `#rehydrate-data`, contributes approximately 822 KB;
  - that script assigns a large array-like hydration payload to `window.__como_rehydration__`;
  - the hydration payload contains extensive profile-card, top-card, vanity, navigation, component, tracking, and application state;
  - the HTML does not expose a clean semantic heading structure for the basic profile.
- Interpretation: the document is a valid direct LinkedIn response and a potential bootstrap/fallback source, but it is substantially larger and noisier than `POST /flagship-web/in/<vanity>/`.
- Decision: prefer the Flagship navigation response for v1; keep document parsing as a later fallback only if replay experiments show the navigation request cannot be generalized.
- Privacy note: the raw HTML and hydration data are not suitable public fixtures.
- Confidence: high.

## EXP-20260830-012 - First direct base-profile replay

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Can the confirmed base-profile request be reproduced outside a browser with a reduced request contract?
- Runtime: dependency-free Python HTTP probe; no browser process involved.
- Target class: operator's own profile using a fresh local authenticated session.
- Result:

```text
HTTP status: 200
Content-Type: application/octet-stream
Response bytes: 366,861
Flight records: 253
Import records: 27
Data records: 226
Top-card anchors: 1
```

- Working request contract:
  - `POST /flagship-web/in/<vanity>/`;
  - JSON `NavigateToScreen` body with resolved vanity arguments;
  - `li_at` and `JSESSIONID` supplied from ignored local environment configuration;
  - CSRF token derived from `JSESSIONID`;
  - `Accept`, JSON content type, Origin, Referer;
  - `X-LI-Anchor-Page-Key`, `X-LI-Initial-URL`, and `X-LI-RSC-Stream`;
  - a generic non-browser user agent.
- Successfully omitted from the working replay:
  - Accept-Language, cache-control, pragma, and priority;
  - all `sec-ch-*` Client Hints;
  - all `sec-fetch-*` Fetch Metadata headers;
  - `X-LI-Application-Instance` and `X-LI-Application-Version`;
  - `X-LI-Layout-Tree`;
  - page-instance and page-instance-tracking headers;
  - page-forest, trace-parent, and trace-state headers;
  - `X-LI-Track` device/client metadata;
  - captured screen hierarchy in the JSON body.
- Safety: the probe logged metadata only and did not print credentials, headers, response bodies, or profile values.
- Interpretation: browser-generated trace, telemetry, client-hint, and build metadata are not required for this request in the tested session.
- Confidence: high for this replay; repeated and non-self validation remain pending.
- Follow-up: minimize the remaining non-authentication headers one at a time, then freeze the v1 transport contract.

## EXP-20260830-013 - Flight decoder compatibility validation

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Does the bounded decoder handle the reference forms present in all captured LinkedIn streams?
- Public test material: synthetic Flight fixture only.
- Unit-test result: 9 dependency-free tests passing.
- Private in-memory validation:

```text
Base profile: parse and record-0 resolution passed (253 records)
Activity: parse and record-0 resolution passed (16 records)
Above Activity: parse and record-0 resolution passed (48 records)
```

- Confirmed decoder behaviors:
  - import and data-record indexing;
  - lazy `$L<record-id>` resolution;
  - `$undefined` and React symbol markers;
  - cross-record and intra-record path references;
  - semantic React tuple path segments such as `props`;
  - cycle, byte, line, record, depth, and resolved-node limits.
- Privacy: real captures were read in memory for validation only and were not copied into the repository or test fixtures.
- Confidence: high for the three captured response shapes.

## EXP-20260830-014 - Embedded component-plan discovery

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Can follow-up profile-card calls be derived from the base response rather than copied from DevTools?
- Result: the base Flight stream contains typed `proto.sdui.actions.core.AsyncComponentRequest` objects with stable `newComponentId` values and typed requested arguments.
- Controlled replay: a component call constructed from the embedded ID, reduced vanity/self-view payload, component ID as `sduiid`, and a locally generated eight-byte base64 span ID returned HTTP 200 and a valid Flight stream.
- Decision: discover and allowlist relevant component IDs from each base response. Never hardcode captured span/page/trace identifiers.
- Confidence: high.

## EXP-20260830-015 - Profile-card section map

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Which server-driven components contain assignment fields?
- Result:

```text
profileCardsExperienceOnly -> experienceTopLevelSection
profileCardsBelowActivityPart1WithoutExp -> education, certifications, projects, volunteering, connected accounts
profileCardsBelowActivityPart4 -> languages, organizations
profileCardsBelowActivityPart7 -> skills
```

- Excluded groups: recommendations, interests, activity, honors/publications, volunteer causes, analytics, promotions, and owner guidance are not part of the assignment schema.
- Confidence: high for the observed build.

## EXP-20260830-016 - Skills detail navigation replay

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Can the full Skills screen be opened directly from the card response?
- Method: located its embedded typed `NavigateToScreen` action and POSTed that action to `/flagship-web/in/<vanity>/details/skills/`.
- Result: HTTP 200, `application/octet-stream`, approximately 563 KB, and 402 Flight records.
- Decoder addition: the screen stores collection state behind observed `$Q`/`$W` Flight collection references, now handled within the existing safety budget.
- Confidence: high.

## EXP-20260830-017 - Pagination serialization contract

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: What exact JSON envelope does the generic pagination action expect?
- Evidence: manual Skills navigation confirmed the route/query, and the first-party JavaScript already loaded by that page exposed its serialization logic.
- Confirmed request body shape:

```json
{
  "pagerId": "<typed pager id>",
  "clientArguments": {
    "payload": {},
    "states": [],
    "screenId": "<current detail screen>",
    "knownTemplateIds": []
  },
  "paginationRequest": {
    "$type": "proto.sdui.actions.requests.PaginationRequest"
  }
}
```

- The full original typed request is retained in both the pagination field and its normalized requested arguments. Undefined Flight values are omitted to match `JSON.stringify`.
- Result: direct replay returned HTTP 200 and ten skill collection items. Continuations are serialized as JSON strings containing the next typed request.
- Confidence: high.

## EXP-20260830-018 - End-to-end normalized profile fetch

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Target class: operator-owned profile, authenticated session, direct Python HTTP client only.
- Result (structural counts only):

```text
name/headline/location/profile image: present
experience: 5
education: 1
skills after pagination: 41
certifications: 0
languages: 0
component warnings: 0
```

- About/background/certifications/languages were absent on the tested profile and normalized as null/empty rather than treated as parser failures.
- Offline regression suite at this checkpoint: 19 tests passing.
- Privacy: no profile response, headers, or credentials were written to tracked files.
- Confidence: high for the operator-owned fixture; authorized non-self layout validation remains a limitation.

## EXP-20260830-019 - Release artifact verification

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Offline regression suite: 20 tests passing.
- Python compilation and whitespace checks: pass.
- Deployment blueprint: parsed successfully with Docker runtime, `/health`, and secret values left unsynchronized.
- Container verification: the production image started as its non-root user; `GET /health` and `GET /openapi.json` both returned HTTP 200.
- Secret audit: `.env`, raw captures, cookie files, and generated packaging artifacts are ignored; no credential values were found in submission files.
- Result: the local artifact is ready to publish. Creating the remote repository/service and supplying hosted secrets remain operator-controlled actions.

## EXP-20260830-020 - HTTP-200 not-found classification

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Research question: Why did an unknown vanity name return `linkedin_protocol_changed` instead of `profile_not_found`?
- Finding: LinkedIn returned upstream HTTP 200 and a valid 172-record Flight stream rather than HTTP 404.
- Stable marker: the SDUI root used `screenId`/`data-sdui-screen` value `com.linkedin.sdui.flagshipnav.infra.NotFound`.
- Rejected signals: the `ErrorPage` module is too broad, and visible text such as “This page doesn’t exist” is localized.
- Implementation: classify the semantic NotFound screen immediately after the base fetch, before discovering or requesting profile components.
- Negative control: a profile screen missing its top card without the NotFound identifier still raises `linkedin_protocol_changed`.
- Verification: live API replay returned HTTP 404 and the stable `profile_not_found` body; 25 offline tests passed.
- Privacy: no raw Flight response or credentials were written to the repository.

## EXP-20260830-021 - Railway locale and Experience RCA

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Symptom: production returned Dutch skill evidence, zero Experience records, and no warning for a profile known to contain jobs.
- Root cause: the reduced request omitted LinkedIn's language header/cookie while extraction still depended on English rendered dates; standalone and grouped Experience entries also used different text order.
- Controlled capture after pinning English: the Experience component was advertised, contained 67 Flight records, exposed the expected semantic section, and contained four outer items representing five roles.
- Fix: request English, parse grouped and standalone layouts separately, warn on non-empty/unparsed Experience sections, retry one transient decode failure, and omit absent response values.
- Live verification: HTTP 200, five correctly titled Experience records, one education record, 41 skills, and no warnings.
- Offline regression suite: 28 tests passing.
- Privacy: only structural counts and synthetic fixtures were retained.

## EXP-20260830-022 - Request-graph latency reduction

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Baseline: 12 sequential LinkedIn calls took 12.24 seconds locally: one base request, five components, one Skills detail request, and five ten-item Skills pages.
- Finding 1: the five component requests are independent after the base response advertises them; a bounded three-worker pool preserves the dependency graph while reducing their wall time.
- Finding 2: changing the typed Skills request count from 10 to 50 returned all 41 observed skills in one 1.51-second page with no continuation. Profiles above 50 still follow the server continuation.
- Optimized result: eight upstream calls took 8.37 seconds locally, a 31.6% reduction, while returning five Experience records, one education record, 41 skills, and no warnings.
- Cache decision: no response cache was added, so every API call remains a fresh LinkedIn read. A short TTL cache remains an optional operational tradeoff if repeated-profile latency becomes more important than immediate freshness.
- Safety: component concurrency is capped at three; dependent navigation and pagination remain sequential.
- Offline regression suite: 30 tests passing.

## EXP-20260830-023 - Length-framed Flight text records

- Timestamp: 2026-08-30 (Asia/Kolkata)
- Status: pass
- Symptom: a legitimate non-self profile consistently returned `linkedin_protocol_changed` during `profileCardsAboveActivity`.
- Isolation: the base profile decoded correctly and advertised all five expected components; the first failing component raised `Malformed tagged record on line 20`.
- Wire finding: record `18` used tag `T` with hexadecimal byte-length prefix `537`. Its raw text payload can contain newlines and is followed by the next Flight record at the declared byte boundary.
- Root cause: the decoder split the entire payload into lines and attempted to JSON-decode every tagged record. This corrupted `T` record boundaries and treated raw text as tagged JSON.
- Fix: parse records from bytes, honor `T<hex-length>,<bytes>` framing, preserve embedded newlines and UTF-8 byte lengths, and resume at the exact next record offset.
- Safety: existing total-byte, record-count, per-record, JSON-depth, resolved-node, cycle, and UTF-8 checks remain enforced; truncated text records are rejected.
- Verification against the reported profile: About present, two Experience records, one education record, 22 skills, two certifications, and zero warnings.
- Offline regression suite: 33 tests passing, including immediate-next-record, embedded-newline/UTF-8, and truncation cases.
- Privacy: only framing metadata and structural result counts were recorded.
