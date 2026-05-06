# Redaction

Use `redact_region(x, y, w, h, reason=None, duration=None)` for sensitive regions.

MVP behavior:

- `duration=None` means the redaction lasts until the end of the recording.
- Use explicit durations for temporary form fields or transient popovers.
- Keep the reason short, such as `email`, `token`, `customer name`, or `internal URL`.
