# Timeline

Timeline events are written to `timeline.json` and are the source of truth for rendered outputs.

MVP event types:

- `chapter`
- `step`
- `caption`
- `click`
- `highlight`
- `redact`

After editing `timeline.json`, run:

```bash
screen-harness render <recording_id>
```
