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

## How the endpoints were found

The solution was built from manual DevTools investigation rather than by
copying an existing LinkedIn scraper library.

The research showed that:

- LinkedIn's current profile page calls `/flagship-web/` endpoints.
- The first response lists the other profile sections that can be requested.
- Each section can be fetched directly without a browser.
- The Skills screen provides instructions for requesting the next page.
- LinkedIn can localize rendered profile text, so the client explicitly requests
  English for consistent extraction.
- Many browser-generated tracking headers are not required for the reduced
  direct request.

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
