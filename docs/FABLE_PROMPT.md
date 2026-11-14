# Prompt for Fable: fix the Claude2Blender bugs, research the field, and take it as far as it can go

Paste everything below the line into the agent. It works in `C:\Users\bentr\Claude4Blender`.

---

## 0. The ambition (read this first)

The owner wants this to become a **truly powerful** product-render tool for Blender, and wants you to **go as far as
you can**. Fix the bugs, build the listed features, and then use your own judgment and **research across the
internet** to bring in the best ideas from other add-ons, tools and papers. Don't stop at the checklist. Be bold
about design and scope, and strict about honesty and safety (section 3 does not bend). Where you choose between
"more features" and "works reliably in the owner's hands", reliability wins, and ambitious extras ship behind a
clearly marked switch or as separate versions.

Order of work: the bugs in section 4 first (the add-on must be trustworthy), then the features in section 5, then the
research in section 6 and whatever it justifies. Start the research early in parallel (it costs little), but don't
let it delay the bugs. Report back at each milestone, not only at the end.

## 1. What this project is

**Claude2Blender** is a Blender 5.x add-on (Windows, owner's machine; macOS and Linux are meant to work too).
Someone with little Blender experience describes what they want in a chat. An AI CLI (Claude Code or Codex,
switchable, default Claude, the user's own sign-in, no API key) proposes a change. The change is **staged**, then
the user presses **Review / Preview / Apply**. Apply goes through a history with exact undo, and a guard
(Allowed Changes, Preserve Geometry) checks every change after it runs. There is also a localhost companion web
page (storyboard, part notes, render queue, review) paired with a key.

The owner uses it on a senior project: a product render of a handheld slide-navigation controller. Reading these
first, in order: `AGENTS.md`, `ASTRA_PROMPT.md` (the original brief, section 3.2 is the escalation rule),
`README.md`, `HANDOFF_BLOCKERS.md`, `docs/NEXT_VERSION.md`, `docs/IMPLEMENTATION_REPORT.md`.

## 2. Current state (verify, don't trust)

- Branch `codex/step-1-decisions-memo` of the owner's fork `Trostky1/Claude4Blender`. Draft PR #1 targets
  `Keegan-mabe/Claude4Blender` `main`. **Never push to Keegan's repo.** Push only to the fork.
- 0.7.0 is what the PR contains (commit `411c86a`).
- **Local, uncommitted** (made on Nov 14): 
  - `0.7.1`: `history.trace()` writes a diagnostic log to `%TEMP%\claude2blender_preview.log` for every preview
    start/end, what ended it (with a stack), undo/redo handler decisions, load_pre clears, and guard rollbacks.
  - `0.7.2`: `guard.py` now allows hiding or showing existing objects when **Full assembly** is on (it used to
    be blocked always). New test in `tests/test_scene.py`; README updated. Version bumped in
    `blender_manifest.toml` and `__init__.py`. `dist/claude2blender-0.7.1.zip` and `-0.7.2.zip` exist.
  - Review these diffs, run the tests, commit them on the branch, and push to the fork.
- Tests: `blender --background --factory-startup --python tests/<file>.py` with Blender 5.3 at
  `C:\Program Files\Blender Foundation\Blender 5.3\blender.exe`. Last known: `test_history.py` 28 checks and
  `test_scene.py` 107 checks pass. Run the whole suite before and after your work and report both.
- Build: `bash build_zip.sh` (uses Blender's extension builder; output in `dist/`). Bump the version for every
  build you give the owner, otherwise Blender and the owner can't tell old from new.
- Owner's real scene for reproduction: `C:\Users\bentr\Documents\SeniorProject_Director.blend`. **Treat it as
  read-only. Copy it to the scratchpad and work on the copy. Never save over it, never render into its output
  path** (an earlier test wrote an image to the scene's saved output path by accident).
- Do not read or change anything under `C:\Senior Project` (school work with its own rules) or
  `C:\Users\bentr\Blender Director` (separate project, read-only reference).

## 3. Rules that must not be broken

1. The add-on stays the source of truth. MCP and companion tools may read state and **stage** proposals; only the
   owner's button in Blender applies anything.
2. Review-before-apply, exact undo, the guard and Preserve Geometry stay intact. Widening what the guard allows
   needs an explicit toggle and a test, never a silent loosening.
3. No secrets, texture packs, HDRIs or licensed assets in the repo (it will become private).
4. Write per-user files with `bpy.utils.extension_path_user`, check `bpy.app.online_access` before any network
   use, keep code readable.
5. **Don't claim something works unless you ran it.** Say "verified" only with test output or a screenshot you
   looked at. Say "not verified" plainly and list why.
6. **Escalation:** after two failed attempts at the same problem, stop, add an entry to `HANDOFF_BLOCKERS.md`
   (what you tried, the error, your suspicion), and move on.
7. Commit messages end with `Co-Authored-By: Fable 5.2 <noreply@anthropic.com>`. Small commits, one per fix or
   feature, each with its tests. Confirm with the owner before pushing if anything outside this brief changed.

## 4. Bugs to fix (in this order)

### 4.1 Preview flashes and disappears, cannot be brought back (highest priority, cause unknown)

**Report:** the owner clicks **Preview** (or Preview then Apply). The change shows for a split second, then goes
away, and Preview can't get it back. Not caused by Preserve Geometry (it was off). Happened in the owner's real
scene in Environment mode, with Cycles Rendered viewport and DLSS viewport denoising on.

**What I know:** something removes the preview right after it starts. Candidates, all unproven:
`_schedule_rollback` (a 0.05 s timer that calls `ed.undo()` after a guard block, in `operators.py`);
`sync_after_native_undo` dropping `_preview` when `undo_post` fires (`history.py`); `_on_save_pre` reverting the
preview and `_on_save_post` failing to re-apply it (autosave or a save); `_on_load_pre` clearing it;
`REGISTER|UNDO` operator flags pushing undo steps that interact with `bpy.ops.ed.undo_push` inside `run_change`;
the viewport re-syncing in Cycles Rendered mode; the Director add-on (also installed, also has handlers).

**Do:**
1. Ask the owner to reproduce on 0.7.1+ and send `%TEMP%\claude2blender_preview.log`. If you already have it,
   read it first. The log lists what ended the preview.
2. Reproduce in a real Blender session if you can (the Browser/computer tools can drive it), not only
   headless, because headless can't use Blender's own undo.
3. Fix the root cause. Add a regression test that survives a simulated undo_post, a save and a viewport redraw.
4. Make failure visible: if a preview is ever dropped for a reason other than the user pressing End Preview or
   Discard, the panel must say why and offer to re-run the preview.

### 4.2 Hiding objects was always blocked (fixed locally in 0.7.2, finish it)

The owner asked for "hide the white floor and props" and got `Blocked by Allowed Changes. Not allowed: hid or
showed D_floor, hid or showed D_prop0 (+2)` even with all 8 toggles on, because hiding existing objects was
forbidden regardless of toggles. 0.7.2 allows it with **Full assembly** on. Finish this properly:
- Confirm the fix in the owner's real scene, not only in `test_scene.py`.
- Decide whether a clearer control is better than reusing Full assembly (for example a separate "Hide/show
  objects" toggle). Don't ship a decision the owner hasn't seen: list the two options in `HANDOFF_BLOCKERS.md`
  or the PR description with a recommendation.
- The blocked message must be readable in the narrow panel: wrap it, or show full text in a tooltip or the
  Details expander. The owner had to guess what "Not al..." said.

### 4.3 The owner can't tell which version is running

After installing 0.7.1 and 0.7.2 the owner twice kept running an old version (Blender keeps old Python loaded
until a full restart, and the panel shows no version). Show the version in the panel header and in
Preferences, and show "restart Blender to finish updating" when the loaded version differs from the installed
manifest version if that can be detected.

### 4.4 Reference note: Enter doesn't send

After adding a reference image with a note, pressing Enter doesn't submit and it isn't clear that
**Generate with Claude** must be pressed. First record exactly what Enter does in that field. Then add a visible
**Send** button beside the note, a hint in the field, and a small "1 image, 1 note" line before sending. Confirm
the note and image travel together in the request (inspect the actual request JSON).

## 5. Features for 0.8.0 (details in `docs/NEXT_VERSION.md`, items 1 to 3)

1. **Choose the model from the UI (Sonnet, Opus, Fable and more).** A dropdown next to the Backend switch in the
   panel and on the companion page.
   - **Claude backend presets:** Fable 5.2 (`claude-fable-5-2`), Opus 5.5 (`claude-opus-5-5`), Sonnet 5.5
     (`claude-sonnet-5-5`), Haiku 5.5 (`claude-haiku-5-5`), "CLI default", and "Custom..." for any other name.
     Verify each ID against the installed `claude` CLI (`claude --help`, a one-line test call) before listing it,
     and hide or grey out any the user's plan can't use. Don't hard-code IDs you haven't checked; keep the list in
     one data file so it can change without a code release.
   - **Codex backend presets:** whatever `codex` reports as available, plus "CLI default" and "Custom...".
   - Remember the choice per backend. Switching backend (including the usage-limit fallback) switches to that
     backend's saved model. Show the active backend and model on every chat turn.
   - **Per-request override:** a small selector on the request so the owner can use a cheaper model for a quick
     tweak and the strongest one for a hard job, without opening Preferences. Consider an "Auto" option that
     picks by task size and says what it picked; keep it off by default.
   - Clear message when the CLI rejects a name; show per-turn latency and, where the CLI reports it, usage.
   Today it is free text in Preferences (`claude_model`, `codex_model`, passed as `--model`).
2. **Paste images as references.** Paste button in the panel, Ctrl+V on the companion page and its chat box,
   saved into the sidecar folder with a generated name. Check first whether Blender's Python can read an image
   from the Windows clipboard without a new dependency (likely not); if not, the companion page is the first
   place to do it, because browsers can. Report what works before building.
3. **Pick more than one mode at once.** Material, Environment and Composition become toggles that can be
   combined in one request, at least one always on. The request lists every selected mode; the guard and
   Preserve Geometry follow the combined set; one Apply and one undo cover the result; old single-mode requests
   and presets still work. This touches `properties.py` (`permissions_for`), `guard.py`, `history.py`, `ui.py`,
   `claude_cli.py`. Design it before editing and write down how permissions combine.

Do these after section 4, in this order: 4.1, 4.2, 4.3, 4.4, then 5.1, 5.2, 5.3, then what section 6 justifies. Ship
each as its own version with its own zip (`0.7.3`, `0.7.4`, and so on) so a regression can be traced to one change.

## 6. Research the field and bring in the best ideas (open internet, go wide)

You may search the web freely and read documentation, source repositories, forum threads, release notes, videos'
transcripts and research papers. The goal is a ranked list of ideas worth building, each with evidence, then
building the best ones.

**Where to look (starting points, not a limit):**
- **Blender product-render and studio-lighting add-ons:** HDR Light Studio and its LightPaint, Light Wrangler,
  HDRI sun and lighting aligners, LeoMoon LightStudio, Poliigon / BlenderKit / Quixel asset flows, Product
  Studio style kits, turntable and camera-rig add-ons, Final Touch, Mule, Photographer, Easy HDRI.
- **AI-in-Blender tools:** BlenderMCP, Anthropic's Blender connector, 3D-Agent, Blender's own AI and Copilot-style
  efforts, any agent that plans, stages, previews and undoes scene edits. Study their tool surface, error handling,
  long-call handling, and what they get wrong.
- **Rendering and finishing:** Cycles / EEVEE product-viz techniques, Blender 5.x compositor and AgX, viewport
  denoising (OptiX, OIDN, DLSS Ray Reconstruction), render farms and queues, quality gates (noise, fireflies,
  clipping), EXR-based relighting and per-light-group finishing.
- **Light and look matching from a reference photo:** single-image lighting estimation, inverse rendering,
  environment-map estimation, material estimation from photos (papers and open implementations).
- **Storyboarding and animation for product films:** shot lists, camera moves, turntables, exploded views,
  light sweeps, motion presets, automatic cut and crossfade.
- **Review and collaboration UX:** comment-on-image tools (Frame.io, Figma-style pins), before/after compare,
  versioned reviews.
- **Asset and materials systems:** non-destructive material libraries, CMF (color, material, finish) boards,
  swap-by-name systems, USD-style variants and variant sets.
- **Add-on engineering:** how the best add-ons handle undo, background work, updates, settings migration, crash
  safety, and testing.

**How to do it well:**
1. **Write findings down as you go** in `docs/RESEARCH.md`: tool or paper, link, date read, what it does, what is
   worth borrowing, what to avoid, license, and whether it fits our rules in section 3. Mark anything you could
   not open or verify.
2. **Prefer primary sources** (the docs, the repo, the paper) over blog summaries. Don't rely on one source for a
   claim that decides a design.
3. **Licensing is relaxed, because this is a private personal tool that isn't distributed.** The owner has decided
   not to worry about open-source license compatibility. You may read, adapt and reuse code from open-source
   projects (GPL included) where it is the best way to do something. Still do these:
   - Record where each borrowed piece came from (project, link, license) in `docs/RESEARCH.md` and in a comment
     at the top of the adapted code, so provenance is never lost.
   - **Never use pirated, leaked, cracked or paid-only code and assets, and nothing proprietary or with no license
     at all** (a repository with no license file is "all rights reserved", not free to use). Don't take paid
     add-ons' code, textures, HDRIs or models.
   - Prefer understanding the technique and writing it fresh when that is about as easy; it keeps the code clean.
   - If the project is ever shared beyond the owner and a small group, or published, this decision must be
     revisited first. Put a line in the README saying so.
4. **Stay inside the rules.** An idea that needs an API key, a cloud service the owner didn't approve, uploading
   the owner's scene or images anywhere, or removing review-before-apply is out. Say so and move on. Never send
   the owner's project files, renders or references to any outside service while researching.
5. **Rank and decide.** End the research with a table: idea, value for product renders, effort, risk, fit with
   our architecture, and your recommendation (build now, later, or skip). Build the top items yourself as
   separate versions, each with tests, a README section and an honest "what it can't do". Put anything large,
   risky or taste-dependent in `docs/NEXT_VERSION.md` for the owner to choose.

**Examples of ambitious directions worth evaluating (pick, adapt, or replace with better ones you find):**
click-a-point-to-place-a-highlight lighting (LightPaint style), an IES and gobo light library, a swap-anything
board (materials, lights, parts, cameras, backdrops by name) with live thumbnails, one-click hero / detail /
exploded / turntable shot packs with quality gates, reference-photo matching for lighting and materials with
measured scores, a render queue with resumable jobs and a contact sheet, variant sets (colorways) that render as
a batch, a CMF board export for the process book, a "why does this look fake?" realism checker (measured, not
vibes), and a shot-by-shot storyboard that drives a Blender animation and an MP4.

## 7. Open validation gates from `HANDOFF_BLOCKERS.md` (do these on Claude)

The previous builder (Codex) logged these as blocked; the brief says to finish them on Claude.

- **B-001** Codex read-only filesystem isolation: can a read-only Codex run read outside the reference folder?
  Test with synthetic marker files only, the exact production invocation, no change to the user's managed
  policy. Report plainly; if broad reads are possible, tell the owner and don't widen permissions.
- **B-002 and B-003** Vision experiment (`docs/VISION_EXPERIMENT.md`, `tests/experiment_refmatch.py`): rerun the
  corrected 12-case suite with real Claude (the `ask()` fix lists image paths in the prompt), validate masks
  before fitting, count rejected masks as failures, keep failed cases, use the predeclared clear-margin
  criterion. If vision shows no gain over the measured fit, say so and keep measured-only as the default.
- **B-004** Live backend smoke test: run `tests/live_backends.py` (four small staging calls, Claude and Codex x
  Material and Environment, disposable scene). Inspect the code, latency and usage per turn and report numbers.
- **B-005** Companion page: desktop and 390 px screenshots of Review, Finish, QA and Pack screens plus
  interaction checks (storyboard save, part notes, queue, chat, paste once it exists). The owner has already
  confirmed pairing and chat work.
- macOS and a second Blender 5.x version can't be tested here: leave the portable branches, mark them
  "not verified" in the report.

## 8. What to return

1. A report in `docs/FABLE_REPORT.md`: each item in sections 4 to 7 as **done and verified**, **done,
   not verified** (why), or **blocked** (entry in `HANDOFF_BLOCKERS.md`). Include test counts before and after.
2. The commits on the fork branch, and the PR description updated.
3. The latest `dist/claude2blender-<version>.zip`, built from committed code, and the exact install steps.
4. For anything visual, screenshots you actually looked at, saved under `docs/examples/`.
5. A short list of what you decided without asking, so the owner can overrule it.
