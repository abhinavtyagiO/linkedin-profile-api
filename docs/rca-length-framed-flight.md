# RCA: legitimate profile returned `linkedin_protocol_changed`

## Summary

A legitimate profile failed while the same deployed API handled another
profile. The base LinkedIn response was valid. The failure occurred in the
`profileCardsAboveActivity` component, which includes About and nearby profile
cards.

## Root cause

The component used a React Flight raw-text record:

```text
18:T537,<raw UTF-8 text bytes><next record>
```

`537` is a hexadecimal byte length. Raw-text records can contain newline
characters, and the next record can start immediately after the declared byte
count.

The old decoder called `splitlines()` on the full response and treated every
tagged record body as JSON. That approach worked for the previously tested
profiles but broke the `T` record into incorrect pieces. JSON decoding then
failed with `Malformed tagged record on line 20`, which the public API correctly
sanitized as `linkedin_protocol_changed`.

## Fix

The decoder now reads the payload as bytes:

1. Read the hexadecimal record ID and tag.
2. For `T`, read the hexadecimal byte length up to the comma.
3. Consume exactly that many bytes as UTF-8 text, including any newlines.
4. Continue at the next byte, which may be the next record immediately.
5. Continue using line-delimited parsing for ordinary JSON/import records.

The existing size, count, depth, cycle, and UTF-8 limits still apply. A text
record whose declared length exceeds the available payload is rejected.

## Verification

- Synthetic tests cover a text record immediately followed by JSON, embedded
  newlines, multi-byte UTF-8 characters, and truncated text.
- The complete authorized request for the reported profile now succeeds.
- Structural result: About, two jobs, one education record, 22 skills, two
  certifications, and no warnings.
- Raw response text and credentials were not retained.
