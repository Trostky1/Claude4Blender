# Research: what other tools do well, and what to bring in

Written November 14, 2026 for Claude2Blender 0.8.x. Each entry says what was read, how much of it, and what
it means for this add-on. "Excerpt" means a search result or a product page was read, not the tool itself.
**None of these tools was installed or run here.** No code, text or assets were copied from any of them.
Nothing from the owner's project was sent anywhere during this research.

## 1. Sources read

| Tool or paper | Link | Read | License | What it does that matters here |
|---|---|---|---|---|
| Light Wrangler | https://superhivemarket.com/products/light-wrangler and https://blenderlighting.com/light-wrangler/docs/ | Product page and docs, excerpts | Paid add-on | Place a light by pointing at the model; scroll for power, Shift+scroll for size; isolate a light; adaptive first size from the selection; auto power when distance changes; 30 IES profiles; flags (negative fill) and gobo stencils; light and shadow linking shortcut. Streams HDRIs and gobos from its own server. |
| HDR Light Studio (LightPaint) | https://www.lightmap.co.uk/learning/hdr-light-studio-quick-start/ and https://help.lightmap.co.uk/hdrlightstudio/blender-workflow-old.html | Search excerpts only | Paid, proprietary | Click on the model where the highlight should be and the light is placed so its reflection lands there. Reflection, illumination and rim modes. |
| Photographer 5 | https://chafouin.gumroad.com/l/photographer5 | Product page, excerpt | Paid add-on | Exposure in real camera terms (ISO, aperture, shutter, EV), physical light units and colour temperature, viewport auto exposure, Light Mixer / World Mixer / Emissive Mixer, per-camera resolution, camera bookmarks, lens shift for verticals, a render queue that renders one or all cameras with incrementing files, light placement on the surface under the mouse. |
| Variant Manager; "Creating product variations in one file" (Christopher 3D) | https://superhivemarket.com/products/variant-manager and https://www.youtube.com/watch?v=1S_T2MS2O84 | Product blurb and video chapter list only | Paid add-on; tutorial | Product variants as named sets (collections, material assignments, cameras) that render in one pass. |
| MCP for Blender (ahujasid, formerly blender-mcp) | https://github.com/ahujasid/mcp-for-blender | Repository page and a registry summary, excerpts | See repository LICENSE (not opened) | Tools: scene info, object info, viewport screenshot, execute arbitrary Python, asset search and download (Poly Haven, Sketchfab, Poly Pizza), text-to-3D generation. Runs code directly; the registry note says to save your work first. |
| Blender Lab MCP Server (Blender Foundation) | https://www.blender.org/lab/mcp-server/ | Whole page | GPL (Blender project) | Official natural-language interface to the Python API for Blender 5.1+. The page carries a security warning: it executes model-written code with no guards, and recommends a virtual machine. Example uses are analysis and housekeeping: polygon count against screen size, renaming datablocks, explaining a node tree, checklist validation. |
| Blender 5.3 release notes, Cycles | https://developer.blender.org/docs/release_notes/5.3/cycles/ | Whole page (short) | CC-BY-SA docs | DLSS viewport denoiser on NVIDIA (driver 620+), viewport only; dispersion in the Principled BSDF; viewport renders pause during final renders; better texture baking. |
| Blender 5.3 overview (80.lv) | https://80.lv/articles/blender-5-3-has-finally-arrived | Article | Editorial | Same as above, plus: the compositor can stack effects like modifiers; a new optional Projects system that tracks more than the open .blend. |
| DiffusionLight / DiffusionLight-Turbo | https://diffusionlight.github.io/ (CVPR 2024), https://arxiv.org/abs/2312.09168 | Project page | Research code on GitHub (license not opened) | Estimates an HDR environment map from one photo by inpainting a chrome ball with a diffusion model and unwrapping it. Needs a GPU diffusion model. |

Not reached in this pass (listed so the gap is visible): LeoMoon LightStudio, Gaffer, Easy HDRI, Poliigon and
BlenderKit add-on flows, Final Touch, Mule, 3D-Agent, Flamenco render farm, Frame.io-style review tools,
USD variant sets, LuxDiT. `docs/RENDER_TECHNIQUES.md` (written earlier by Codex) already covers lighting and
material technique from other sources and was not re-checked here.

## 2. What this means

**Where Claude2Blender is already ahead.** Every general AI-in-Blender tool read here runs model-written code
directly. The Blender Foundation's own page tells users to use a virtual machine because nothing guards their
data. Staged proposals, Preview, exact undo, Allowed Changes and Preserve Geometry are this add-on's real
difference. They should be protected and advertised, not traded away for speed.

**Where it is behind.** The lighting add-ons are much better at *direct manipulation*: point at the model, a
light appears there, scroll to change it. Photographer is better at *camera language* (EV, ISO, colour
temperature) and at rendering many cameras in one go. Variant tools are better at "same product, six
colourways, one click". Claude2Blender has pieces of each (a mirror-solved light placement, a render queue for
storyboards, presets) but none is as quick to reach as in those tools.

**Ideas worth taking, with how they fit:**

| # | Idea | Seen in | Value for product renders | Effort | Risk | Fit | Recommendation |
|---|---|---|---|---|---|---|---|
| 1 | **Colourways / variants**: name a set of material choices for the same product ("Blue", "Orange", "White"), switch between them, render them all as a batch with the same camera and lights | Variant Manager, Christopher 3D | Very high. The owner's project has three CMF boards and needs the same shot in each. | Medium | Low. Material swaps already go through History. | Good: a variant is a stored proposal (`assign_material` per part) applied through the normal path. | **Build next.** |
| 2 | **Scene check ("why does this look fake?") before rendering**: measured checks with a fix suggestion each. Examples: no bevel on hard edges, objects not on the floor, default grey material left on a part, light clipping, camera lens wider than 50 mm for a product, unapplied scale, a 60 m floor under a 17 cm product. | Blender Lab MCP's analysis examples, `RENDER_TECHNIQUES.md` failure catalogue | High. Catches the common beginner faults without taste judgments. | Medium | Low. Read-only; each fix is a staged proposal. | Good: extends the existing measured QA. | **Build next.** |
| 3 | **Camera language**: exposure in EV, white balance in kelvin, lens presets (50 / 85 / 100 mm product lenses), lens shift to keep verticals straight, per-camera resolution | Photographer | High for a beginner: these are the words photographers and tutorials use. | Small to medium | Low | Good: `c2b.exposure` and `c2b.camera` exist; needs kelvin and shift helpers and panel presets. | Build soon. |
| 4 | **Render all cameras**: one button renders every marked camera at the chosen size, with files named by camera and an incrementing version | Photographer render queue | High. The owner asked for an 8K still by hand in this session. | Small | Low. Runs in a background Blender on a copy (already how storyboard renders work). | Good: reuse `render_queue.py`. | Build soon. |
| 5 | **Click-to-place light, scroll to adjust** in the viewport | Light Wrangler, HDR Light Studio, Photographer | High for lighting by eye. | Medium to large (modal operator, cannot be tested headless) | Medium: modal viewport tools are fiddly and need hands-on testing. | Partly there: mirror-solved placement exists as a tool the agent can call. | Later, with the owner testing each step. |
| 6 | **Flags and gobos**: negative fill cards and shadow patterns as named, editable objects | Light Wrangler, Photographer | Medium. Shapes reflections on glossy plastic, which this product has. | Medium | Low | Good as `c2b.flag(...)` and a generator. No bundled textures: procedural patterns only. | Later. |
| 7 | **Auto power when a light moves** (keep perceived brightness when distance changes) | Light Wrangler | Medium | Small | Low | Good inside `c2b.light`. | Later, small. |
| 8 | **IES profiles** | Light Wrangler, Photographer | Low for studio product shots (softboxes, not fixtures). | Small | Asset licensing | Weak | Skip unless a lifestyle set needs it. |
| 9 | **Environment map from one photo with a diffusion model** | DiffusionLight | Possibly high for matching a reference photo. | Large: a multi-gigabyte model and a GPU pipeline outside Blender. | High: heavy dependency, and it invents plausible lighting instead of measuring it. | Poor fit with "measure, don't guess" and "self-contained". | **Skip for now.** Keep the measured light-basis fit as the default; revisit only if the vision experiment shows the fit is the bottleneck. |
| 10 | **Asset search and download from inside the tool** (Poly Haven, ambientCG CC0 textures and HDRIs) | MCP for Blender | Medium: real HDRIs and scanned textures lift realism. | Medium | Needs network access and a choice the owner has not made (downloads from third-party sites). | Allowed by licence (CC0) but touches the "nothing online unless approved" rule. | Ask the owner first. |
| 11 | **DLSS viewport denoiser switch** in the add-on's Preview | Blender 5.3 | Small: the owner already turns it on by hand. | Small | Viewport only; needs driver 620+. | Fine | Later, small. |
| 12 | **Text-to-3D model generation** | MCP for Blender | None here: the product is real CAD. | n/a | n/a | n/a | Skip. |

## 3. Decision

Build **1 (colourways)** and **2 (scene check)** now, as separate versions with tests. 3 and 4 are the next
two. 5 to 7 need the owner at the keyboard and are listed in `docs/NEXT_VERSION.md`. 9 and 12 are skipped,
with the reason above. 10 needs the owner's decision.

## 4. What could not be verified

- Every "what it does" above comes from the tools' own pages or search excerpts. None was run, so claims
  about how well they work are the vendors', not checked.
- Licences of the two research code bases and of MCP for Blender were not opened. Nothing was taken from them.
- The HDR Light Studio help page and the Light Wrangler video were not read in full.
