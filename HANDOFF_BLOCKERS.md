# Handoff blockers

## 2026-11-14 handoff status

The local studio preview and regression work progressed through every brief
section, but the items below prevent calling the full request production-complete.
See `docs/IMPLEMENTATION_REPORT.md` for passed tests and exact boundaries.

## B-001 — Codex read-only filesystem isolation not established

- **Date / scope:** 2026-11-13; ASTRA step 1 privacy finding, Windows,
  Codex `0.169.0-alpha.11.1` bundled app CLI.
- **Trying to establish:** whether read-only execution can read outside the
  reference workspace. The sole target was a synthetic marker created for the
  test, not a personal file.
- **Attempt 1:** `codex sandbox -c 'sandbox_mode="read-only"' -C <workspace>
  powershell.exe ... Get-Content <outside-marker>`.
  Failed: `the following required arguments were not provided:
  --permission-profile <NAME>`.
- **Attempt 2:** corrected to `codex sandbox --permission-profile ':read-only'`
  with the same marker and approved runtime access.
  Failed: `windows sandbox failed: registered Core launch requires an installed app`.
- **Suspect:** app-packaged CLI sandbox-launch integration differs from the
  standalone CLI/documented platform helper. Cause not established. The separate
  image-only `codex exec` test succeeded but executed no filesystem tool.
- **Impact:** cannot certify reference-only reads or conclude that all disk
  locations are readable. Do not silently ship broader permissions. This does
  not block designing the backend or stand-in tests.
- **Next:** recommend doing this on Claude, using a supported CLI/sandbox setup
  and controlled inside/outside marker fixtures on Windows and macOS. Test the
  exact production invocation and restricted-read profile without changing the
  user's managed policy. Stop after the two attempts recorded here for this pass.

## B-002 — Claude experiment harness omitted image paths

- **Trying:** score arms B/C/D on the synthetic references with real Claude.
- **Attempt 1:** case 0 granted the image folder but omitted paths from prompt.
  Response said no image was received; JSON parsing failed at line 1 column 1.
- **Attempt 2:** case 1 with the same harness also returned explanatory text;
  parsing failed at line 1 column 1. Stopped the provider loop after two failures.
- **Cause:** builder's harness error. Unlike Codex image flags, the Claude Read
  workflow needs explicit paths in the text. This does not measure Claude vision.
- **Prepared correction:** `ask()` now lists ordered image paths. Not rerun here.
- **Next:** recommend doing this on Claude. Run the corrected 12-case suite and
  preserve failed cases; do not treat the current partial result as final.

## B-003 — Codex vision-prior masks prevented product extraction

- **Trying:** improve measured fit through a light/mask prior and one critique.
- **Attempt 1:** case 1 prior: `Could not find the product in the reference. Try
  a reference with a plain background`.
- **Attempt 2:** case 6 correction returned the same product-extraction error.
  Stopped after the second failure. Other cases' scores are preserved.
- **Suspect:** model bounding boxes constrain the fit to unsuitable regions;
  the current segmentation heuristic is sensitive to the prior. Not proved to
  be a general vision limitation. B/C do not consistently improve paired A.
- **Next:** recommend doing this on Claude. Validate masks before fitting,
  count rejected masks as failures, then finish both providers with independent
  rerenders and a predeclared clear-margin criterion. Default remains measured-only.

## B-004 — Live adapter end-to-end smoke blocked by approval-service limit

- **Trying:** four small real CLI staging calls (Claude/Codex × Material/Environment)
  in a disposable scene, after fake-CLI flows passed.
- **Result:** automatic approval review rejected execution because its usage
  limit was reached. The review could not complete; it did not judge the command
  unsafe. The action did not run and was not retried through another path.
- **Ready:** `tests/live_backends.py`. No changes are applied by this smoke test.
- **Next:** once approval service access is restored, run the prepared test and
  inspect code/latency/usage. Recommend doing this on Claude if the current
  builder remains unavailable. Earlier image/experiment calls are narrower evidence.

## B-005 — Validation gates still unavailable or outside completed scope

- **Companion finish review:** paired storyboard/note UI checked at desktop and
  390px. Browser tool disappeared before expanded review screens could be
  recaptured. Fresh reviewer disposition: `recapture`. Its source findings
  (draft loss, QA approval invalidation, stale image requests) were fixed, but
  source inspection cannot certify layout or browser behavior. Need desktop and
  390px Review/Finish/QA/Pack screenshots plus interaction checks.
- **macOS / Blender 5.x matrix:** no Mac runtime or other Blender 5.x runtime
  was available. Portable command/locking branches are implemented, not verified.
- **Owner thin slice:** known fixture correction and the explicitly approved
  48-frame demo rendered. Live model-proposed correction and user-operated pin,
  Preview/Apply remain unverified end to end.
- **Quality:** no claim of production realism, independent noise validation,
  continuous multi-shot motion, calibrated AgX Finish preview or exhaustive
  design knowledge. Demo first/last stills were inspected, not motion playback.
- **Persistence:** exact undo stays in-session. Save As carries JSON but does
  not move old capture folders; rerender in the new project before review/Pack.
- **Next:** recommend doing this on Claude for the missing visual/runtime pass.
  These are pending validation gates, not invented two-attempt failures.
