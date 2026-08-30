# LinkedIn Profile API

This project was built for the Tross hiring assignment. Send it a LinkedIn
profile URL and it returns the profile information as clean JSON.

The running application talks directly to LinkedIn over HTTP. It does not open
a browser and it does not read profile-page HTML. Chrome DevTools was used only
during research to understand which requests LinkedIn makes.

This is not LinkedIn's official API. It uses undocumented endpoints used by
LinkedIn's own website, so those endpoints can change without warning.

## What the API returns

- Name, headline, location, and About
- Profile and background image URLs when available
- Work experience and education
- Skills, including all available skill pages
- Licenses, certifications, and languages when available
- A timestamp, section status, and safe warnings

Fields that LinkedIn does not return are left out of the JSON. The API does not
send `null`, empty lists, empty nested objects, or empty optional subfields.

The response does not include analytics, recommendations, tracking IDs,
editing buttons, private prompts, or LinkedIn's raw response.

## Try the API

### Production curl

```bash
curl --silent --show-error \
  --request POST 'https://linkedin-profile-api-production-190f.up.railway.app/v1/profiles:fetch' \
  --header 'Content-Type: application/json' \
  --data '{"profile_url":"https://www.linkedin.com/in/abhinav-tyagii/"}' \
  | jq .
```

Replace the profile URL with the LinkedIn profile you want to fetch. If `jq`
is not installed, remove the final `| jq .`; it only formats the output.

### Request

```http
POST /v1/profiles:fetch
Content-Type: application/json
```

```json
{
  "profile_url": "https://www.linkedin.com/in/example-person/"
}
```

### Example response

```json
{
  "profile_url": "https://www.linkedin.com/in/example-person/",
  "vanity_name": "example-person",
  "name": "Example Person",
  "headline": "Software Engineer",
  "location": "Bengaluru, Karnataka, India",
  "images": {
    "profile": "https://media.licdn.com/..."
  },
  "experience": [
    {
      "title": "Software Engineer",
      "company": "Example Company",
      "employment_type": "Full-time",
      "date_range": "Jan 2025 - Present",
      "duration": "1 yr",
      "location": "Bengaluru, Karnataka, India",
      "description": "Built ...",
      "company_logo_url": "https://media.licdn.com/..."
    }
  ],
  "skills": [
    {
      "name": "Python"
    }
  ],
  "metadata": {
    "fetched_at": "2026-08-30T00:00:00+00:00",
    "completeness": {
      "top_card": "complete",
      "experience": "present",
      "skills": "present"
    }
  }
}
```

While the server is running, API documentation is available at `/docs` and
the health check is available at `/health`.

### Errors

Every expected error has the same shape:

```json
{
  "code": "linkedin_rate_limited",
  "message": "LinkedIn rate limited the request",
  "retryable": true
}
```

Common responses include:

| Status | Code | Meaning |
|---:|---|---|
| 404 | `profile_not_found` | The LinkedIn profile does not exist |
| 422 | `invalid_profile_url` | The supplied URL is not a supported LinkedIn profile URL |
| 502 | `linkedin_protocol_changed` | LinkedIn returned a response the parser does not understand |
| 502 | `linkedin_unavailable` | LinkedIn or the network could not complete the request |
| 503 | `linkedin_authentication_failed` | The saved LinkedIn session has expired |
| 503 | `linkedin_challenge_required` | LinkedIn returned a login or verification page |
| 503 | `linkedin_rate_limited` | LinkedIn limited the request rate |

LinkedIn sometimes returns HTTP 200 even when a profile does not exist. In that
case its response identifies the page as
`com.linkedin.sdui.flagshipnav.infra.NotFound`. The application recognizes that
screen and returns the expected 404 response. It does not depend on English
error text, which may change with language settings.

## Local setup

Python 3.9 or newer is required.

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
```

Add these values to `.env` from a LinkedIn session that you own and are allowed
to use:

```text
LINKEDIN_LI_AT=<value>
LINKEDIN_JSESSIONID=<value>
```

Do not add extra quote characters around `JSESSIONID`. The application uses it
to build LinkedIn's CSRF header. Neither value is printed by the application.

Start the server:

```bash
.venv/bin/python -m uvicorn linkedin_profile_api.app:app \
  --host 127.0.0.1 \
  --port 8000
```

Call it from another terminal:

```bash
curl --silent --show-error \
  --request POST 'http://127.0.0.1:8000/v1/profiles:fetch' \
  --header 'Content-Type: application/json' \
  --data '{"profile_url":"https://www.linkedin.com/in/example-person/"}'
```

Add `| jq` to format the JSON output.

## How it works

```text
Profile URL sent to this API
  -> validate the URL
  -> load the LinkedIn session from environment variables
  -> request the main profile data from LinkedIn
  -> decode LinkedIn's React Flight response
  -> find the profile sections advertised in that response
  -> request independent profile sections with at most three parallel calls
  -> request Skills in pages of up to 50 until there are no more
  -> extract only the fields in our public response
  -> return clean JSON
```

LinkedIn's `/flagship-web/` responses are not ordinary profile JSON. They use a
format called React Flight, which is a list of records with references between
them. Some raw text records use an explicit byte length and can contain
newlines, so `flight.py` reads the stream by record framing rather than simply
splitting it into lines. It then safely follows references. The rest of the
application finds the relevant sections and turns their visible data into the
stable response shown above.

The main files are:

- `app.py`: public API routes and error responses
- `client.py`: authenticated HTTP requests to LinkedIn
- `flight.py`: React Flight response reader
- `protocol.py`: request creation and LinkedIn action discovery
- `extract.py`: profile field extraction
- `service.py`: coordinates the full request flow and Skills pagination
- `models.py`: public request and response fields

### Latency

A profile fetch requires several dependent LinkedIn requests, so an uncached
response takes seconds rather than milliseconds. Independent profile sections
are fetched with a conservative three-request pool. The Skills request asks for
up to 50 items per page instead of LinkedIn's advertised default of 10, while
still following a continuation when a profile has more skills.

On the authorized test profile, this reduced the local uncached request graph
from 12 calls and 12.24 seconds to 8 calls and 8.37 seconds. No profile-response
cache is used, so each API call still reads current data from LinkedIn.

## Step-by-step approach used

The solution was built by studying LinkedIn's own web requests. An existing
LinkedIn scraper library was not copied or wrapped.

1. **Set the boundary.** The required input was a LinkedIn profile URL and the
   required output was clean profile JSON. A browser could be used for manual
   research, but it could not be part of the running application.
2. **Observe one profile load.** Using an operator-owned LinkedIn account,
   Chrome DevTools was cleared and one profile was opened. This isolated the
   requests caused by that action.
3. **Map the request flow.** The profile used `/flagship-web/in/<vanity>/` for
   its main data and `/flagship-web/rsc-action/actions/component` for sections
   such as About, experience, education, languages, and Skills. Skills also
   used a separate detail request and pagination action.
4. **Record the contract safely.** The method, path, query names, useful
   headers, request-body shape, and response type were documented. Cookies,
   CSRF values, raw personal data, and request-specific IDs were kept out of
   source control.
5. **Replay the request without a browser.** The captured request was rebuilt
   in Python and authenticated with `li_at` and `JSESSIONID` values loaded only
   from environment variables. This proved that a normal HTTP client could
   fetch the same data directly.
6. **Remove unnecessary browser data.** Headers were removed one at a time.
   Browser client hints, page tracking, tracing, and build metadata were not
   needed. The application kept only the small set required for a reliable
   authenticated request.
7. **Decode LinkedIn's response.** The response was React Flight data rather
   than ordinary JSON. A bounded decoder was written to read its records,
   follow references, and correctly handle length-prefixed text that may
   contain newlines.
8. **Follow actions returned by LinkedIn.** Component and pagination requests
   are discovered from typed actions in the preceding response. This avoids
   copying short-lived page IDs and lets Skills continue across pages.
9. **Extract only profile fields.** Each useful section is allowlisted and
   converted into the public response model. Analytics, editing controls,
   recommendations, promotions, tracking data, empty lists, and null values
   are not returned.
10. **Handle failure cases.** Expired sessions, verification pages, rate
    limits, network failures, and changed response formats receive stable API
    errors. LinkedIn sometimes reports a missing profile inside a successful
    HTTP 200 response, so its semantic `NotFound` screen is translated into the
    API's `404 profile_not_found` response.
11. **Test the behavior.** Synthetic response samples cover parsing,
    extraction, pagination, URL validation, error mapping, and safety limits.
    A metadata-only live check confirms the current request flow without
    storing real profile responses.
12. **Deploy with secrets outside the code.** The same browser-free client runs
    in the hosted service. Railway supplies the two LinkedIn session values as
    secret environment variables and exposes the FastAPI application over
    HTTPS.

The important result is that the browser was only an observation tool during
research. Every production profile fetch is made directly by the HTTP client.

More detail is available in the [experiment log](docs/experiment-log.md),
[protocol notes](docs/protocol-notes.md), and
[design and research plan](docs/design-and-research-plan.md).

## Tests

Run the offline test suite with:

```bash
.venv/bin/pytest -q
```

The tests use made-up response samples. Real LinkedIn responses are not stored
in the repository because they contain personal data and request metadata.

To check the live protocol without printing profile data or credentials:

```bash
PYTHONPATH=src .venv/bin/python scripts/replay_profile.py example-person
```

The tests cover response decoding, reference limits, URL validation, component
discovery, Skills pagination, field extraction, public API responses, and the
special HTTP-200 not-found response used by LinkedIn.

## Docker and deployment

Build and run the included Docker image:

```bash
docker build -t linkedin-profile-api .
docker run --rm -p 8000:8000 \
  -e LINKEDIN_LI_AT \
  -e LINKEDIN_JSESSIONID \
  linkedin-profile-api
```

The repository also includes `render.yaml`. To deploy on Render, create a
Blueprint from this repository and enter the two LinkedIn values as secret
environment variables in the Render dashboard.

Never place the credential values in source control, `render.yaml`, Docker
build arguments, screenshots, logs, or CI output.

The Docker command uses one application worker because all requests share one
LinkedIn session. Before increasing that number, add account separation and a
careful request-rate limit.

## Limitations

- The application uses undocumented LinkedIn endpoints. LinkedIn may change
  them at any time.
- It uses a LinkedIn website session, not an official API token. Sessions expire
  and may trigger login verification.
- LinkedIn may limit or block automated requests. Use the project only where
  authorized, and review LinkedIn's terms and relevant privacy laws.
- Returned fields depend on profile privacy, the signed-in account, language,
  and LinkedIn's current page layout.
- Missing or invisible LinkedIn fields are omitted from the response.
- Work-history entries grouped under one company are rendered differently from
  standalone jobs and still need more layout coverage.
- The current extractor has been live-tested mainly with the session owner's
  profile. More authorized profile layouts should be tested.
- Automatic session renewal and challenge solving are intentionally not
  implemented.

## Security choices

- Only `https://linkedin.com/in/<profile>/` and
  `https://www.linkedin.com/in/<profile>/` inputs are accepted.
- Response size, record count, line size, nesting depth, and resolved record
  count are limited before data is processed.
- Authentication values are read from environment variables or the ignored
  `.env` file.
- LinkedIn response bodies and authentication headers are not logged.
- Raw captures, HAR files, copied cURL requests, and cookie files are ignored by
  Git.

## Production issue RCA

The Railway deployment initially returned Dutch skill evidence and no
Experience entries. The client had removed LinkedIn's language header and
cookie while reducing the captured browser request, but the extractor still
expected English labels and month names. The Experience parser also treated
standalone jobs like grouped-company jobs, causing company names to be used as
titles.

The fix pins the LinkedIn response language to English, handles both Experience
layouts separately, reports a warning if visible jobs cannot be parsed, retries
one transient unreadable Flight response, and omits absent values from public
JSON. See [the full RCA](docs/rca-localized-experience.md).
