# LinkedIn Profile Protocol Notes

Last observed: 2026-08-30

## Current protocol hypothesis

The authenticated LinkedIn web build observed during this assignment uses a server-driven UI under the `/flagship-web/` namespace. This differs from the older `/voyager/api/graphql` model commonly described in prior reverse-engineering material.

The working request graph is currently:

```text
/in/<vanity>/
  -> /flagship-web/in/<vanity>/
  -> /flagship-web/rsc-action/actions/component
       ?componentId=<profile component name>
       &sduiid=<request-scoped value>
       &parentSpanId=<trace/request value>
  -> rendered profile cards

/in/<vanity>/details/skills/
  -> /flagship-web/in/<vanity>/details/skills/
  -> /flagship-web/rsc-action/actions/pagination
       ?sduiid=<request-scoped value>
       &parentSpanId=<trace/request value>
```

This graph is now reproducible outside the browser for the base profile,
allowlisted components, Skills detail screen, and Skills pagination.

## Confirmed base-profile request

Client-side navigation from Feed to a profile issues:

```text
POST /flagship-web/in/<vanity>/
```

The JSON body is a typed `NavigateToScreen` action targeting the Profile screen and `profile_view_base`. Its `requestedArguments` resolve the vanity name, while the screen hierarchy records the source Home screen and destination Profile screen.

The response is a large React Flight stream containing the profile top card and profile-level UI state. Basic identity fields are rendered into the SDUI/React tree rather than exposed through semantic `firstName`, `lastName`, and `headline` keys.

The request has now been reproduced successfully outside the browser. The confirmed response content type is `application/octet-stream`.

### First working reduced header set

```text
Accept: */*
Content-Type: application/json
Cookie: li_at + JSESSIONID from environment
Csrf-Token: derived from JSESSIONID
Origin: https://www.linkedin.com
Referer: https://www.linkedin.com/in/<vanity>/
X-LI-Anchor-Page-Key: d_flagship3_feed
X-LI-RSC-Stream: true
User-Agent: generic non-browser identifier
```

The direct replay succeeded without browser Client Hints, Fetch Metadata,
initial URL, application instance/version, layout tree, page instances,
page-forest/tracing headers, or `X-LI-Track`. This is the frozen v1 contract;
it is intentionally described as reduced rather than the theoretical absolute
minimum.

The top-card decoder must:

1. index all Flight records;
2. locate `com.linkedin.sdui.impl.profile.components.topCard` or the stable `profile-top-card` view anchor;
3. follow lazy and path references;
4. traverse the resolved React/SDUI subtree;
5. extract only normalized identity, headline, location, image, and canonical-link fields;
6. discard editing controls, analytics, premium prompts, recommendations, tracking, and UI state.

## Document bootstrap

`GET /in/<vanity>/` returns the HTML application shell. Its `#rehydrate-data` script assigns a very large hydration array to `window.__como_rehydration__` and contains broad profile/application state. This is a useful validation source but is not the preferred v1 protocol because it is larger and more coupled to the full web shell than the Flagship navigation response.

## Confirmed Activity request

The Activity component is requested with `POST`:

```text
/flagship-web/rsc-action/actions/component
```

Its query selects the component and supplies request-scoped identifiers:

```text
componentId=com.linkedin.sdui.generated.profile.dsl.impl.profileCardsActivity
sduiid=<request-scoped-value>
parentSpanId=<request-scoped-value>
```

The JSON body passes `vanityName` and `isSelfView` under `clientArguments.payload`, plus empty `states` and `knownTemplateIds`, typed `requestMetadata`, and an SDUI `screenId`.

The capture confirmed authenticated cookies, a CSRF header,
`X-LI-RSC-Stream: true`, page/build metadata, and trace metadata. Direct replay
later proved the captured page/build/trace values were not required.

The Above-Activity component extends this body with replaceable-section arguments and a typed `profileComponentState`. Its state bindings use `com.linkedin.sdui.components.core.BindingImpl` and `MemoryNamespace`; these appear to describe client UI lifecycle behavior and should initially be replayed only if experiments prove they are required.

## Confirmed response format

The Activity response is React Flight/RSC wire data. The captured example contains newline-delimited records of two broad kinds:

- `I` records mapping record IDs to client module imports/exports;
- data records containing React element arrays, references, props, and nested LinkedIn SDUI models.

The main data tree uses `$`-prefixed record references and typed protobuf-derived objects such as:

```text
proto.sdui.common.RequestMetadata
proto.sdui.actions.requests.RequestedArguments
proto.sdui.actions.core.Navigate
proto.sdui.actions.core.NavigateToScreen
proto.sdui.actions.core.NavigateToUrl
proto.sdui.actions.core.SetState
proto.sdui.triggers.Trigger
proto.sdui.triggers.ClickTrigger
proto.sdui.navigation.ScreenHierarchy
```

Observed Flight token forms include:

- `"$"` as the React element marker;
- `"$L<hex-record-id>"` as a lazy module/record reference;
- `"$undefined"` as an undefined-value sentinel;
- long `$0:...:props:...` paths as references into previously decoded model-tree locations.

A safe decoder must distinguish these tokens from ordinary strings and resolve references only after all records have been indexed. It should also enforce depth, record-count, and payload-size limits before traversing an untrusted upstream response.

Therefore, the current parser design is:

```text
raw response bytes
  -> Flight line/record reader
  -> record table and reference resolver
  -> React/SDUI tree traversal
  -> component-specific field extractor
  -> stable public profile model
```

The raw captured payload must not be used as a public fixture because it contains personal profile values and tracking metadata.

## Candidate endpoint roles

| Route pattern | Provisional role | Evidence status |
|---|---|---|
| `/flagship-web/in/<vanity>/` | Main profile navigation and top-card Flight response | confirmed POST |
| `/in/<vanity>/` | Full HTML shell with `window.__como_rehydration__` bootstrap | confirmed GET; fallback only |
| `/flagship-web/in/<vanity>/details/skills/` | Full Skills data/view response | observed |
| `/flagship-web/in/<vanity>/details/education/` | Full Education data/view response | observed |
| `/flagship-web/rsc-action/actions/component` | Named server-driven profile card | observed |
| `/flagship-web/rsc-action/actions/pagination` | Pagination for detail collections | observed on Skills |
| `/flagship-web/rsc-action/actions/server-request` | Generic server action | role unknown |
| `/flagship-web/rsc-action/actions/app-config` | Application configuration | likely not profile data |
| `/flagship-web/rsc-action/actions/server-stream-request` | Session/stream infrastructure | likely not profile data |

## Component map

| Component ID suffix | Confirmed/provisional content | Extraction policy |
|---|---|---|
| `profileCardsActivity` | Recent activity card | Exclude from assignment response unless explicitly requested later |
| `profileCardsAboveActivity` | Composite upper cards: About, Featured, Analytics, Suggested for You, services, and sales/highlight surfaces | Allowlist About/Featured candidates; discard analytics, recommendations, promotions, and private/self-only cards |
| `profileCardsExperienceOnly` | Experience | Normalize public experience entries |
| `profileCardsBelowActivityPart1WithoutExp` | Education, certifications, projects, volunteering, connected accounts | Normalize education/certifications only |
| `profileCardsBelowActivityPart4` | Languages and organizations | Normalize languages only |
| `profileCardsBelowActivityPart7` | Skills summary and Skills-detail navigation | Normalize summary, then follow typed detail pagination |

`profileCardsAboveActivity` demonstrates why the external API must not expose a generic recursive rendering of LinkedIn's SDUI tree. The response mixes assignment-relevant profile information with owner analytics, dynamic actions, promotional surfaces, tracking metadata, and UI-only state.

## Semantic not-found response

An unknown vanity name does not necessarily produce an upstream HTTP 404. In
the current Flagship build, LinkedIn returned HTTP 200 with a valid Flight
stream whose root identified the screen as:

```text
com.linkedin.sdui.flagshipnav.infra.NotFound
```

The same response contained an `ErrorPage` module and localized visible copy,
but neither is sufficiently specific for classification. The service therefore
uses only the semantic NotFound screen ID to return public HTTP 404. A valid
Flight response with a missing top card but no NotFound screen remains a
protocol error, preserving change detection.

## Remaining unknowns and hardening work

The implemented request graph is proven for an operator-owned profile. Remaining
hardening targets are stable top-card positions across authorized non-self and
localized profiles; private/challenged response fixtures; long-list
pagination caps; and determining whether more reduced base headers can be
removed. These must be tested experimentally rather than inferred from older
scraper recipes.

## Confirmed Skills pagination

The Skills detail action is embedded in the Part 7 card response as a typed
`NavigateToScreen`. The detail response advertises category-specific typed
`PaginationRequest` objects. The `ALL` request uses `start` and `count` payload
fields; each response may carry the continuation request as a JSON string.

The generic pagination endpoint receives a JSON body containing `pagerId`,
normalized `clientArguments`, and the full original `paginationRequest`. This
was verified both in LinkedIn's current first-party client module and by a
successful direct replay. Pagination is bounded by the service and stops when
no continuation is returned.

## First-party bundle clue

A public JavaScript bundle loaded by the profile page contains a general XMLHttpRequest helper with the following behavior:

```text
POST <url>
Content-Type: application/json
Csrf-Token: derived from JSESSIONID
credentials: included
body: string input or JSON.stringify(input)
```

This evidence now agrees with captured and replayed component/pagination calls:
JSON POST bodies, CSRF derived from `JSESSIONID`, and credentialed same-origin
requests.

## Next validation capture

Use an authorized non-self profile with the network log cleared and save the
following sanitized facts:

1. whether the top-card text order differs from the operator-owned layout;
2. which assignment components are advertised;
3. empty/private section behavior;
4. response status and content type for private profiles;
5. locale-dependent date and UI-label differences.

Keep the capture local and replay through the implemented secret-safe client.
