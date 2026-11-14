# Step 1 — decisions memo

2026-11-13 · Design proposal before implementation · `codex/step-1-decisions-memo`

Scope follows ASTRA revision 3: one GitHub-only Claude2Blender add-on, Blender 5.x+,
Windows/macOS, Claude by default with a Codex dropdown, subscription sign-in, and
human review before scene execution. Steps 2 onward are not implemented here.

## Backend and result contract

Use a Blender-independent `Backend` interface: `probe()` returns availability,
version and sign-in state; `build_command(turn)` returns argv, stdin, child
environment and working directory; `stream(job)` yields normalized events;
`parse_result()` validates the final result; `cancel(job)` terminates its process
tree. Only `ClaudeBackend` and `CodexBackend` know CLI flags, event formats or
provider error parsing. Generic UI uses backend IDs/display names.

Normalize progress, usage, result, error, cancellation and completion by request
ID; distinguish auth, quota, timeout, malformed output and transport errors.
The add-on sends current scene/permissions, pending proposal, relevant transcript
and references every turn, without CLI resume. Quota offers a user-triggered
switch retaining context; no automatic provider retry or partial-output staging.

Keep the existing strict result shape `{summary, code, message, material, scene}`
in a shared schema module. **All three object levels already require every field
and forbid extras.** Preserve enums and `""`/`-1`/`"n/a"` defaults. Validate output
and Python syntax before staging; empty code means conversation. Scene execution
stays behind Preview/Apply, History and guards; reject stale results.

## Local server, MCP and state

Python HTTP server binds `127.0.0.1` on an OS-assigned port; a stdio MCP shim exposes
only `get_context`, `list_notes`, `get_storyboard`, `get_queue`, `proposal_status`
and `stage_proposal`. No apply, preview-execution, arbitrary-code execution,
deletion or render-start tools. Validate bounded inputs and request/revision IDs;
queue work for Blender's main-thread timer. Companion metadata edits use the
same queue. Scene edits from either client stage proposals; storyboard approval
and render start are explicit user actions in Blender.

Use a per-run local capability token in an owner-restricted runtime file, outside
Git/URLs; check Host/Origin and bound requests/assets. Configure only this MCP
server, excluding inherited tools/hooks. Check `bpy.app.online_access` before
provider calls; scope localhost separately. Record latency and reported usage.

Store `<project>.c2b/state.json` plus `thumbnails/` beside a saved blend. JSON v1:
`schema_version`, `project_id`, `revision`, `blend_fingerprint`, `conversation`,
`notes`, `storyboard`, `proposals`, `history`, `render_queue`. Records use stable
IDs/revisions; notes identify object/face/local position and proposal; shots record
camera, frame range and approval revision. Assets remain external paths. Use atomic
writes, backup and single-instance ownership; unsaved/read-only projects use
`extension_path_user`. Persist history metadata, but **current exact undo is
in-memory**; cross-reopen undo needs separately tested snapshot storage.

## Findings and owner decisions

Installed Codex `0.169.0-alpha.11.1` supports noninteractive exec, stdin, images,
JSONL, schema and final-output flags. A live synthetic-image probe returned the
correct colors/positions and the complete existing schema in **5.6 seconds**.
Sign-in reports ChatGPT; key overrides were removed from the child environment.
Read-only is not evidence of reference-only privacy: the local isolation probe
could not launch. Require a verified restricted-read policy before claiming that
boundary; never silently expand access. Evidence and sources: [verification](STEP1_VERIFICATION.md).

**Owner decisions still needed:** (1) whether broader local reads are acceptable
if reference-only isolation cannot be verified (recommend requiring isolation);
(2) whether exact undo across reopen is a v1 requirement (recommend session undo
plus clearly labeled persistent audit history initially). All other settled
choices stand. Neither decision blocks the backend abstraction or fake-CLI tests.
