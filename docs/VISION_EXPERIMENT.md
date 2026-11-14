# Vision-assisted lighting experiment — partial result

Run on Windows / Blender 5.3.0, 2026-11-14. Harness:
`tests/experiment_refmatch.py`; numeric observations: `experiment-results.json`.
References are synthetic Cycles renders with known setups, not generated images.

Twelve cases vary key direction, height, color, number of lights, source size and
world contribution on a rounded box/sphere fixture. A uses the existing measured
fit. B restricts lights/mask using a model prior. C asks for one comparison-based
correction. D uses model-estimated RGB weights alone. Both providers use the same
strict result schema. Real provider failures are recorded, never replaced with
mock answers.

| Arm | Completed cases | Median linear RGB RMSE | Paired A median RMSE | Cases beating A |
|---|---:|---:|---:|---:|
| A, measured only | 12 | 0.04102 | — | — |
| B, Codex prior | 7 | 0.06337 | 0.02966 | 3 / 7 |
| C, Codex correction | 5 | 0.05957 | 0.01747 | 2 / 5 |
| D, Codex weights | 7 | 0.19659 | 0.02966 | 0 / 7 |

Median strongest-light angular errors: A 25°, B 52°, C 43.96°, D 52°.
The medians use different available subsets; compare each arm to its paired A
column, not the full A median. Residuals per product/rim/background are retained
in the JSON. No invented match percentage is reported.

## Failures and interpretation

Claude cases 0 and 1 returned non-JSON explanations because the harness omitted
reference paths from its text prompt, even though image folders were granted.
This is a harness failure, not evidence that Claude cannot interpret images.
The path list is corrected for handoff, but was not rerun after the two failures.

Codex mask/region suggestions failed product extraction on case 1 and on the
correction for case 6. The run stopped after the second failure as required by the
brief. No Claude scored cases and only partial Codex cases means the requested
both-backend experiment is **incomplete**. Completed cases do not justify adding
vision priors to the default path. Keep measured matching; retain the manual,
reviewed critique command as an experimental aid with no promised gain.

## Limits of this measurement

Image difference compares linear combinations of captured basis renders against
the reference, not an independently rerendered final proposed scene. Direction
error scores the strongest light, which is ambiguous for multiple-light scenes.
The fixture is deliberately simple; it does not establish behavior on glossy,
textured products or busy lifestyle backgrounds. Softness varies across three
captured source-size sets; it is not a fully optimized joint shape/lighting fit.
The run did not pre-register a numeric clear-margin threshold, so its results
must not be advertised as a confirmatory keep/drop decision.

For the follow-up, fix the image-path harness, retain invalid masks as failures,
run all 12 cases on both providers, and rerender candidates independently. Before
that run, set a criterion such as at least 10% paired median RMSE improvement
without worse angular error, and report failure rate as well as successful cases.
Recommend doing this on Claude; see B-002 and B-003 in the handoff.
