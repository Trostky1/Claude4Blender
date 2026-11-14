# Product-render techniques and executable decisions

Research pass: 2026-11-13. Scope: Blender 5.x, editable product scenes, measured
reference matching. **Production quality is a set of checks plus human judgment,
not a promised realism percentage.** Values below are starting ranges to test,
not universal optical truth. Do not copy or redistribute any source's imagery,
HDRIs, texture packs or prose.

## Scene and setting: start with the product's job

The default set should explain the product's silhouette, interfaces, material and
scale. Choose a sweep for a clean silhouette, tabletop for contact/reflections,
or a contextual set when a prop explains use. Background, support surface and
lighting are separate editable components. Avoid a random prop catalogue: every
prop needs a scale cue, use cue or composition purpose. This is our design rubric,
to be tested across products, not a sourced guarantee of taste.

| Finding / design rule | Add-on action | Review / limitation |
| --- | --- | --- |
| A sweep removes the hard floor-wall seam; tabletop reflection can ground the object | `c2b.backdrop(kind="sweep"/"floor")`, named set recipe | Check contact, horizon and reflected silhouette; preserve the user's floor |
| White versus black cards control reflected contrast, especially on shiny surfaces | Separate editable card/flag objects; reflection placement tool | The [broncolor setup](https://broncolor.swiss/news/the-ultimate-product-photography-lighting-setup) recommends choosing card tone for product contrast; don't add more lights to fix every reflection |
| A prop should clarify scale or use rather than compete | Recipe has optional prop count/spacing and an explicit material | Human scene-believability review stays mandatory |
| Frame the actual shape, then reserve copy space intentionally | Framing fill fraction, center offset, margins from the object mask | Thirds/centering are options, not automatic grades; clipping is a separate failure |
| Camera height reveals top surfaces and changes apparent stance | Named hero/detail/profile/lifestyle camera templates | Keep sensor size with lens; a guessed lens from a single image is ambiguous |
| Exploded views explain assembly | Existing `c2b.explode`, selected movable parts only | Check intersections and parent motion; never infer assembly travel as ground truth |
| Brand fit depends on reference and intended message | Store a short brand/CMF brief in the conversation and storyboard | Require a human review item; do not score brand fit from a histogram |

Use low-contrast backgrounds to see dark product outlines and dark backgrounds
to show selected bright contours only when that serves the brief. A bright sweep
must retain a controlled product shadow; a dark set must retain enough silhouette
separation. Both are evaluated against the shot's intent, not the same luminance
target. For camera behavior, see the [Blender camera documentation](https://docs.blender.org/manual/en/5.0/render/cameras.html).

## Lighting: shape reflections before adding complexity

| Technique | Executable mapping | Validation |
| --- | --- | --- |
| Large area sources soften shadows and create readable reflected shapes | Seeded area-light recipe with independent azimuth, elevation, size and distance | Check penumbra and highlight shape against reference |
| A strip gives a long highlight; a broad softbox describes a broad plane | `c2b.light` RECTANGLE size/size_y parameters | Surface normal and roughness also affect the observed shape |
| Fill controls shadow contrast, not just overall brightness | Key/fill/rim multipliers; measure lit/shadow regions if correspondence is known | A nominal watt ratio is not a measured surface luminance ratio |
| Flags and gobos selectively remove or pattern light | Named editable geometry/texture masks in the knowledge roadmap | Keep out of camera or intentionally part of the set; test shadow artifacts |
| Light linking isolates a difficult surface | Explicit include/exclude recipe, never silently linked | Version-specific testing required; not part of the first recipe implementation |
| HDRI provides environment reflections; area lights provide directed art control | External HDRI path plus editable light rig | Never bundle HDRIs; record license/source in the user's asset folder |
| Highlight placement follows reflection geometry | `lightpaint_position(point, normal, camera, distance)` | Solves a mirror direction, not roughness, occlusion or extended-source footprint |
| Caustics are costly and scene-dependent | Enable selectively for a glass/resin shot, otherwise flag a deliberate approximation | [Cycles light settings](https://docs.blender.org/manual/en/5.0/render/cycles/light_settings.html) describes selective shadow-caustic settings |

Suggested exploration bounds: key azimuth ±60° camera-relative, elevation 20–70°,
source width 0.5–3 product radii, fill 0.05–0.5 key energy, rim 0–1 key energy.
These are **our generator bounds**, not claims of a correct setup. Recipes store
the seed and parameters so comparisons can be repeated. Calibrate energy against
physical scale and a rendered preview; don't treat exposure as a material fix.

## Materials and nodes

The [Principled BSDF](https://docs.blender.org/manual/en/5.0/render/shader_nodes/shader/principled.html)
provides the surface layers; the add-on's existing material presets remain the
starting point. Physical texture scale and variation are more actionable than
asking a model for a vaguely “realistic” material.

| Surface issue | Add-on action | What the gate can / cannot establish |
| --- | --- | --- |
| Injection-molded ABS or rubber looks uniformly perfect | Procedural roughness/bump variation in named node groups; external scanned packs when available | Detect absence of connected variation; cannot prove the process or polymer |
| Fingerprints, dust and scratches | Optional sparse masks at a stated scale, separately adjustable | Never default to making every product dirty; verify close-ups |
| Coated paint and resin | Separate base/coat roughness and transmission/IOR parameters | Inspect highlight layering, thickness and internal paths |
| Brushed metal | Controlled anisotropy plus consistent tangent direction | Test rotating the object/light; anisotropy alone does not produce machining marks |
| Fabric | Sheen plus weave-scale variation; geometry where silhouette needs fibers | Bump cannot produce a true fuzzy silhouette |
| Glass / translucent plastics | Transmission, absorption/thickness, appropriate bounces | Wrong normals and missing thickness can dominate apparent material error |
| Edge sharpness | QA flags missing bevel evidence for human inspection | Beveled topology may exist without a modifier; avoid automatically modifying CAD |
| Normal versus displacement | Use bump for shading detail, displacement only when geometry/silhouette requires it and permission allows | [Bump node](https://docs.blender.org/manual/en/5.0/render/shader_nodes/displacement/bump.html) changes normals; it does not replace real geometry |
| Texture tiling / scale | Real-unit mapping, repeat scale, and on-demand texture pack lookup | Compare material features against known object dimensions |

Maps describing data (normal, roughness, displacement) need appropriate data
interpretation, while color textures need their actual color-space interpretation.
Do not change a project's working space to fix one material. See [color spaces](https://docs.blender.org/manual/en/5.0/render/color_management/color_spaces.html).

## Rendering and post

Use Cycles for the production path and low-resolution checks before expensive
output. Adaptive sampling stops spending samples on converged regions; test
noise thresholds against the difficult glossy/transmission regions, not only a
clean background. Denoising is useful but can remove small texture details.
Two independent noisy renders give a better noise estimate than the variance of
one image, which also contains real texture. [Sampling](https://docs.blender.org/manual/en/5.0/render/cycles/render_settings/sampling.html)

AgX compresses a wide scene range and desaturates highly exposed colors. Keep the
view transform fixed during comparison; a Standard-view reference and an AgX
output cannot be judged as equivalent raw RGB. Filmic and Standard remain useful
when intentionally chosen for the pipeline. Blender 5.0 also offers ACES views;
the tool must not assume that AgX is the only modern option. [Displays and views](https://docs.blender.org/manual/en/5.0/render/color_management/displays_views.html),
[Blender 5.0 changes](https://developer.blender.org/docs/release_notes/5.0/color_management/)

Production mapping:

- **Noise:** paired-render estimate when available; otherwise report unmeasured.
- **Highlights/blacks:** measure clipping after the chosen display transform and
  separate product/background masks. A white background can intentionally clip.
- **Depth of field:** focus the feature that sells the shot; inspect the label and
  interaction surfaces. Avoid using blur to conceal a modeling error.
- **Motion blur:** test moving frames and transitions, including thin parts.
  Check adjacent frames for noise/denoiser flicker; one still is not animation QA.
- **Glare/bloom, vignette, lens aberration and grain:** optional finishing layers,
  not a realism prerequisite. Keep neutral export and post settings separate.
- **Light groups:** capture independent contributions for finishing; reweight
  their linear RGB before display transformation. This cannot move a light or
  recreate a different shadow geometry. [Render passes](https://docs.blender.org/manual/en/5.0/render/layers/passes.html)
- **Render queue:** use a temporary blend copy, explicit output folder, per-job
  log, completion manifest and QA status. Missing frames are failures.
- **Animation:** follow the bundled storyboard-first workflow. Every new shot
  arrangement invalidates approval. Use one monotonic curve per move; don't
  mistake a two-frame integration test for a production animation review.

## Measurements ranked by payoff / effort

| Priority | Measurement | Reliability and use |
| --- | --- | --- |
| 1 | Product fill, center, border margins from object mask | High for our pass; reference mask may fail. Controls framing and clipping warnings |
| 1 | Luminance percentiles, display clipping, contrast | High as image statistics; does not identify “correct” exposure without intent |
| 1 | Background vertical luminance profile | High with a valid background mask. Controls sweep falloff/gradient comparison |
| 2 | Known scene units/dimensions and source sizes | High for our geometry, not for unknown reference dimensions |
| 2 | EXIF focal length/aperture/exposure | Useful metadata when present; cropping, sensor size and processing still matter |
| 2 | Reference-vs-render RMSE in the same color space and framing | Reproducible, but penalizes harmless misalignment and cannot replace taste |
| 3 | Shadow direction/length/penumbra | Reliable on simple known planes; ambiguous geometry and mixed sources reduce confidence |
| 3 | Highlight shape, position, rim width | Useful on known normals; confounded by roughness, environment, metal tint and clipping |
| 3 | Paired-render noise / adjacent-frame instability | Good with controlled seeds and identical scene; textures confound single-frame estimates |
| 4 | Surface frequency, anisotropy, grain period | Only meaningful when spatial scale and perspective are known |
| 4 | White balance / source temperature | Product reflectance and mixed light make one-image estimates ambiguous |
| 4 | Focal length, elevation, DOF and motion blur from one reference | Framing/depth ambiguity; prefer EXIF and known geometry |
| 5 | Monocular estimated normals/depth | New dependencies and uncertain metric scale; defer until measured gains justify them |

Analysis by synthesis should compare the same features on normal/depth/index/AO/
light-group passes from our own scene, retaining a confidence value for reference
estimates. Specular/diffuse balance and falloff are useful when the corresponding
passes are available, not quantities to invent from arbitrary JPEG pixels.

## Failure catalogue and gate

The gate returns **fail**, **needs review**, or **pass** per check, with values and
thresholds. Thresholds are tunable project policy. Empty/missing evidence never
passes silently. Block completion for missing camera/output/frames, nonfinite
pixels, severe unintended product clipping, and known invalid unit dimensions.
Require manual sign-off for material believability, edge softness, composition,
brand fit, meaningful props, and animation continuity.

Typical CG signals: razor edges, scale-inconsistent grain, flat frontal light,
floating contact, oversaturated highlights, uniformly perfect surfaces, extreme
DOF on a catalogue shot, arbitrary lens artifacts, and an empty set where a use
cue is needed. Map each to a named parameter or a human review item; never claim
the automated gate can detect all of them.

## Verification limits

The web reader returned HTTP 402 for direct Blender manual pages twice; indexed
official excerpts supplied the technical source checks above. Full-page reading
of those URLs was not established in that pass. Source links identify the owning
documentation; recipes/rubric choices are explicitly our hypotheses. Blender's
current manual redirects/version labels can drift, so executable tests target
the installed 5.3.0 build. Light linking, caustic workflows, animation denoising
and novel scene taste remain unverified here, not advertised as implemented.
