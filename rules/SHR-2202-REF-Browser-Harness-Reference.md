# REF-2202: Browser Harness Reference

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Active

---

## What Is It?

A design reference extracted from `browser-use/browser-harness` for shaping Screen Harness. This is not a code-copying guide. It records the product and architecture logic that should influence Screen Harness: thin core, editable agent workspace, plain-file reusable skills, and a small CLI surface.

---

## Content

Reference inspected:

- Repository: `https://github.com/browser-use/browser-harness`
- Commit: `30d54b7216c7d0b818e55d573e216e949a9099a4`
- Commit date: `2026-05-05T12:07:28-07:00`
- Local reference path during analysis: `/tmp/browser-harness-ref`


## Relevant Shape

Browser Harness is organized around a small protected core plus an editable workspace:

- `src/browser_harness/run.py`: tiny CLI wrapper for `browser-harness -c '<python>'`.
- `src/browser_harness/helpers.py`: short core helper API, pre-imported into `-c` scripts.
- `src/browser_harness/admin.py`: install, doctor, update, daemon/session admin.
- `src/browser_harness/daemon.py`: long-lived browser/CDP bridge, only because browser control needs persistent IPC.
- `agent-workspace/agent_helpers.py`: executable helpers the agent is allowed to edit.
- `agent-workspace/domain-skills/`: reusable site-specific playbooks, stored as Markdown.
- `interaction-skills/`: reusable interaction guidance, also Markdown.
- `SKILL.md`: day-to-day agent usage.
- `install.md`: installation and troubleshooting.

Approximate core size at the inspected commit:

| File | Lines |
|------|------:|
| `run.py` | 110 |
| `helpers.py` | 493 |
| `_ipc.py` | 181 |
| `daemon.py` | 406 |
| `admin.py` | 782 |

The headline lesson is not the exact line count. It is the boundary: most task-specific intelligence is kept out of the protected core.


## Principles To Borrow

1. Keep the primary agent interface as `screen-harness -c '<python>'` with helpers pre-imported.
2. Keep `run.py` small. It should dispatch `-c`, `doctor`, and a few admin commands, not become a framework.
3. Keep core helpers short and explicit. Add primitives only when they are broadly useful.
4. Let the agent edit `agent-workspace/agent_helpers.py`, not protected package files.
5. Load agent helpers at process startup. Avoid hot reload in the first version.
6. Prefer plain Markdown skills for reusable process knowledge. Use Python helpers only when the reusable asset is executable behavior.
7. Split `SKILL.md` from `install.md`: usage belongs in the skill; setup and troubleshooting belong in install docs.
8. Make `doctor` actionable. It should check real dependencies and show the next concrete fix.
9. Use environment variables and `.env` files before adding a large config system.
10. Add a daemon only when the product truly needs a long-lived controller.


## Screen Harness Adaptation

Screen Harness should copy the logic, not the implementation.

Recommended v0.1 adaptation:

- `screen_harness/run.py`: CLI and `-c` execution.
- `screen_harness/helpers.py`: recording and timeline primitives exposed to agents.
- `screen_harness/recorder.py`: FFmpeg subprocess wrapper.
- `screen_harness/timeline.py`: safe timeline writes and schema helpers.
- `screen_harness/render.py`: FFmpeg rendering from timeline events.
- `screen_harness/captions.py`: SRT/ASS from explicit caption events.
- `screen_harness/admin.py`: `init`, `doctor`, and helper management.
- `agent-workspace/agent_helpers.py`: executable local helpers.
- `agent-workspace/domain-skills/<system>/<flow>.md`: reusable SOP playbooks, selectors, field names, style guidance, and traps.
- `interaction-skills/`: reusable screen-recording mechanics, such as redaction, captions, highlights, timing, and permission troubleshooting.

Screen Harness should not add a daemon in MVP v0.1. Browser Harness needs a daemon because the browser/CDP session is a persistent external target. Screen Harness can initially run a recording subprocess inside a single `-c` process and finalize files at the end. A daemon becomes justified later for global hotkeys, menu bar controls, multi-process recording control, or live preview.


## Differences From Browser Harness

- Browser Harness acts on a live browser. Screen Harness produces durable media artifacts.
- Browser Harness optimizes for immediate page state verification. Screen Harness must preserve provenance: every final overlay should trace back to `timeline.json`.
- Browser Harness domain skills are per-site playbooks. Screen Harness domain skills should be per-application or per-business-flow SOP playbooks.
- Browser Harness can recover from stale browser sessions. Screen Harness must recover from interrupted FFmpeg processes and partially written recording directories.
- Browser Harness helper mistakes affect the current browser task. Screen Harness helper mistakes can expose local files, audio, and screen recordings, so helper-diff visibility is more important.


## Planning Consequences

- MVP v0.1 should be deterministic: manual or agent-authored captions first, AI rewrite later.
- The first reusable knowledge format should be Markdown domain skills, not Python modules.
- The first implementation should prove one reliable recording-to-rendering loop before adding hotkeys, ASR, GUI, or automatic redaction.
- The implementation should include `SKILL.md` and `install.md` early, because this product is meant to be used by agents as much as by humans.

---

## Change History

| Date       | Change                                                     | By    |
|------------|------------------------------------------------------------|-------|
| 2026-05-06 | Initial version                                            | —     |
| 2026-05-06 | Filled reference analysis from browser-use/browser-harness | Codex |
