# RCA: missing Experience data on Railway

## Summary

The Railway API returned a valid profile with education and 41 skills, but its
`experience` field was empty. Skill evidence was rendered in Dutch. A separate
request briefly returned `linkedin_protocol_changed` before the next request
succeeded.

## User impact

- Valid Experience data was omitted from the public response.
- Some returned evidence text used an unexpected language.
- A transient unreadable LinkedIn response failed the whole request.
- Missing fields were represented as `null` or empty lists, making absence hard
  to distinguish from useful data.

## Root causes

### 1. The reduced HTTP request did not set a language

The browser capture contained both an `Accept-Language` header and LinkedIn's
`lang` cookie. They were removed while reducing the request because they did
not appear necessary for authentication. On Railway, LinkedIn then returned
Dutch rendered text.

The extractor matched English month names and several English UI labels. Dutch
date text did not match the date detector, so Experience items contained no
recognized date rows and were skipped.

### 2. Experience has two different layouts

The live English response showed:

```text
Grouped company:
company -> employment summary -> location -> title -> date -> ...

Standalone job:
title -> company and employment type -> date -> location -> ...
```

The previous parser always used the line immediately before a date as the job
title. That works for grouped roles but selects the company line for standalone
roles.

### 3. Empty extraction was treated like an absent section

The component was fetched and contained Experience items, but parsing produced
an empty list. The response reported `empty_or_not_public` with no warning, so a
parser failure looked like a genuinely empty profile section.

### 4. Public models used visible empty defaults

Optional fields defaulted to `None` and collections defaulted to empty lists.
FastAPI serialized those defaults, even when LinkedIn had not returned the
corresponding data.

### 5. A LinkedIn read response was briefly unreadable

One request returned a response that the Flight decoder could not parse, while
an immediate repeat succeeded. Because all of these actions only read profile
data, one retry on a decode failure is safe and bounded. Authentication,
challenge, rate-limit, timeout, and other HTTP failures are not retried.

## Fixes

- Send `Accept-Language: en-US,en;q=0.9`.
- Send LinkedIn's `lang=v=2&lang=en-us` cookie.
- Parse grouped-company and standalone Experience layouts separately.
- Add a warning when visible Experience items produce no parsed jobs.
- Retry a Flight decode failure once, then return the existing protocol error.
- Exclude `None`, empty default lists, empty default objects, and empty nested
  default fields from successful API responses.

## Verification

- The offline suite contains 28 passing tests.
- A full authorized local HTTP call returned five Experience records with these
  title classes: two grouped-company roles and three standalone roles.
- The same call returned one education record and 41 skills.
- Absent About, certifications, languages, background image, empty skill
  evidence, and empty warnings were omitted from JSON.
- No raw LinkedIn response or credential value was added to the repository.

## Prevention

- Treat locale headers and cookies as part of the response contract whenever
  extraction depends on rendered text.
- Keep fixtures for every observed section layout.
- Warn when a section contains items but extraction returns none.
- Continue validating the public JSON response, not only internal models.
