# DevTools Capture Checklist

The Chrome extension can control the page but cannot read Chrome's Network panel. The operator must perform this one capture manually.

## Capture one main-profile component request

1. Open the operator's own LinkedIn profile in Chrome.
2. Open Chrome DevTools and select **Network**.
3. Enable **Preserve log**, then clear the log.
4. Filter for `rsc-action`.
5. Reload the profile once.
6. Select one request whose URL contains:

```text
/flagship-web/rsc-action/actions/component
```

Prefer a request whose `componentId` begins with:

```text
com.linkedin.sdui.generated.profile.dsl.impl.profileCards
```

## Record only sanitized structure

Add a new experiment entry containing:

- HTTP method;
- sanitized path;
- query-key names;
- non-personal `componentId` value;
- request header **names**;
- content type;
- request-body key/type shape, if any;
- response status and content type;
- top-level response shape or wire-format description;
- initiator filename/function, if shown.

Do not paste header values yet.

## Local replay material

Chrome's **Copy as cURL** output contains live session secrets. Keep it only under `work/private-research/`, which is ignored by Git. Before letting Codex inspect it:

- replace the **entire** `Cookie`/`-b` value with `<REDACTED_COOKIE_HEADER>`; do not attempt to preserve individual cookies;
- replace the entire CSRF header value with `<REDACTED_CSRF_TOKEN>`;
- redact `X-LI-Application-Instance`, page-instance/tracking IDs, page-forest IDs, trace headers, and any other request/session correlation values;
- redact the value of `X-LI-Track` if device metadata is not needed;
- the vanity identifier with `<vanity>` if the exact value is not required for the experiment;
- any internal member URN with `<profile-urn>`;
- request-scoped identifiers with `<request-scoped-value>` unless replay requires them.

A safe structural capture should contain a line similar to:

```text
-b '<REDACTED_COOKIE_HEADER>'
-H 'csrf-token: <REDACTED_CSRF_TOKEN>'
```

Placeholders for actual replay belong only in a local `.env` file, never in a shared cURL or committed document.

Never commit the original cURL, HAR, cookies, or raw response.
