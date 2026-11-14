# Step 1 verification and implementation constraints

Date: 2026-11-13 (America/Chicago). This is evidence for the decisions memo,
not a claim that the backend switch, companion or persistent history is built.

## Sources inspected

- Repository `ASTRA_PROMPT.md` and the requested Downloads copy have identical
  SHA-256: `C565C8E61F87453EB4D5B9C3CC137986CFF454EAAB6D4781640876D3F1961044`.
- `README.md`, `COMPARISON_AND_PLAN.md`, `AGENTS.md`, bundled animation skill.
- `claude2blender/claude_cli.py`: schema, command construction, image preparation,
  worker queue, sign-in, environment filtering and session resume.
- `bridge.py`: syntax-check-only staging API; `operators.py`: guarded execution;
  `history.py`: in-memory snapshots and save/load behavior; `tests/test_generate.py`.
- No Blender Director files were modified; no user blend was opened.

## Local Codex findings

Installed CLI: `codex-cli 0.169.0-alpha.11.1`, bundled with the Windows Codex app.
`codex login status` returned **Logged in using ChatGPT**. No authentication file
or token was read by the probe code.

Local `codex exec --help` confirms `--json`, `-o/--output-last-message`,
`--output-schema`, `--image/-i`, `--sandbox read-only|workspace-write`, stdin via
`-`, `--ephemeral`, and `--ignore-user-config`. It also lists `resume`; using it
is unnecessary for portable add-on-owned conversations.

The live probe used a programmatically drawn 192x96 PNG (red left, blue right),
the exact `RESULT_SCHEMA` extracted without importing the add-on, a separate
working folder, and this command shape:

```text
codex exec --ignore-user-config --ephemeral --sandbox read-only
  --skip-git-repo-check -c project_doc_max_bytes=0 -c web_search="disabled"
  --json --output-schema <schema.json> -o <result.json>
  -C <probe-workspace> -i <fixture.png> -
```

The prompt requested image description only, no tools, and empty code. The child
environment omitted `CODEX_API_KEY`, `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`;
it retained the CLI's ordinary sign-in location, without copying credentials.

First launch failed because the outer editing sandbox disallowed Codex runtime
writes. An approved launch outside that outer sandbox, still retaining the
child's `--sandbox read-only`, succeeded: exit 0, 5.6 seconds, correct red-left /
blue-right description, all expected result fields, and an empty `code` value.
The stream contained `thread.started`, `turn.started`, `item.completed` with an
`agent_message`, and `turn.completed`. Final JSON was also written by `-o`.
Reported usage: 15,038 input tokens, 94 output tokens, zero cached input tokens.
This is one CLI smoke test, not representative chat latency or a vision-quality
evaluation. Only PNG was exercised; macOS and other image formats remain untested.

Probe files are local and ignored under `tests/out/step1/`. They contain synthetic
data, not reference photos. The fixture is test data, not an image-model reference.

## Privacy finding and unresolved runtime check

Do **not** interpret `--sandbox read-only` or a separate cwd as a reference-folder
allowlist. Current permission profiles offer explicit read restrictions, with
platform and managed-policy caveats. `--sandbox` selects the older sandbox
configuration in ordinary configurations; don't combine it blindly with a
restricted-read profile. These are documented capabilities, not verified local
isolation. [Permission profiles](https://learn.chatgpt.com/docs/permissions)

A deterministic probe attempted to read only a harmless marker one directory
outside its working folder. Attempt 1 used `sandbox_mode="read-only"` but this
CLI's sandbox helper requires `--permission-profile`. Attempt 2 used its built-in
`:read-only` profile and failed before command execution with
`windows sandbox failed: registered Core launch requires an installed app`.
Stopped after two failures; see [HANDOFF_BLOCKERS.md](../HANDOFF_BLOCKERS.md).
Thus **whole-disk readability was not measured**, and no reference-only guarantee
is established. The legacy CLI flag and newer profile must each be verified on
supported Windows/macOS versions with outside-folder read and inside-folder
write-denial fixtures before shipping privacy claims.

The existing Claude runner's `Read`/`--add-dir` construction also needs an actual
outside-folder denial test; its comments alone are not proof of an exclusive
read boundary. New MCP access must remain independent of broad filesystem/shell
access. Managed requirements must be respected, never worked around.

## Official documentation cross-check

- [Noninteractive mode](https://learn.chatgpt.com/docs/non-interactive-mode):
  exec, JSONL event types, schema/file output, saved CLI auth and the per-run
  `CODEX_API_KEY` override. This supports hiding API-key overrides by default.
- [CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli):
  image attachment and command options. Prefer installed `--help` when syntax
  differs; the sandbox helper differed from the documentation example here.
- [Approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security):
  sandbox versus approval policy and OS-specific enforcement. Noninteractive
  operation must fail visibly if permissions are insufficient, not request an
  interactive approval or expand the sandbox.

## Baseline tests

Windows, Blender **5.3.0**, build `02f0899d78e3`; factory startup, no user file:

| Command (using the installed Blender executable) | Result |
| --- | --- |
| `blender --background --factory-startup --python tests/test_generate.py` | 38 checks passed |
| `blender --background --factory-startup --python tests/test_headless.py` | 28 checks passed |
| `blender --background --factory-startup --python tests/test_history.py` | 28 checks passed |

All three exited 0. Blender emitted an extension-cache permission warning; the
assertions completed. The headless test intentionally exercises a failing
proposal (`RuntimeError: boom`); that is its error-reporting check. No production
code changed, so this is a selected baseline, not the full render suite. macOS,
live UI rollback, real quota errors and live Claude were not tested in this step.

## Step 2 acceptance gates

Extend fake-CLI headless coverage for both providers: strict schema validation,
Material/Environment staging and guarded Apply/Undo, conversation transfer after
quota, auth versus quota errors, cancellation/timeouts, late-event rejection,
oversized stdin prompts and key filtering. Check `bpy.app.online_access` before
provider calls. Keep blocking I/O off Blender's main thread. Refresh request and
scene revisions before retry/apply so old proposals cannot target a changed scene.

Before enabling the companion/MCP slice: test token/Origin checks, request limits,
path traversal, untrusted note text, duplicate/stale proposals, two-instance
ownership, save-as/reload recovery, and approved storyboard revision enforcement.
Store token files separately from portable sidecar state. Treat serialized code
and notes as untrusted data; restoring a sidecar must never execute its contents.
