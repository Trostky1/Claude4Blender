# Claude2Blender

A sidebar in Blender's 3D viewport for working with Claude or Codex. Write a prompt,
pick what you want changed, select objects or faces, attach reference photos,
and press **Generate with Claude**. Claude's change shows up for review, and
nothing runs until you press **Apply**. Every applied change goes into a
History with Undo and Redo.

Existing review-and-apply workflows:

* **Material matching.** Select an object, or faces in Edit Mode, add a photo
  of a material, and Claude builds a photorealistic shader for exactly that
  selection. Preview it on the real object, refine it ("more matte", "grain
  50% smaller"), then apply.
* **Environment matching.** Add a reference photo and Claude recreates its
  lighting, background and studio look as real, editable Blender lights, a
  procedural world and a backdrop. Nothing is a picture pasted behind your model.
* **Composition matching.** Claude matches a reference's camera angle and
  arrangement, including exploded views of multi-part products.
* **Allowed changes.** Toggles decide what Claude may touch (for example
  lighting and background but not the camera). Anything outside them is taken
  back automatically.
* **Safe by default.** Claude never runs code on its own. Preview flips between
  **Original** and **Proposed**, Preserve Geometry stops accidental mesh edits,
  and every change can be undone.

## Studio preview (v0.7.0)

This branch adds a backend dropdown (Claude by default), owned conversation history,
explicit quota switching, and a paired localhost studio board. Notes, storyboard
and audit metadata live beside the project in `<name>.c2b/`; exact scene undo is
available within the current Blender session.

The studio board supports part/surface notes, notes mapped from rendered pixels,
numbered shots, captured-light Finish previews, measured QA and reviewed delivery
Packs. Generated changes always wait for Blender's **Preview / Apply** controls.
MCP exposes only reads and proposal staging. The approved storyboard renders in a
background Blender copy, with PNG frames, EXR passes and an MP4 preview.

**Validation preview, not a production-certified release.** See
[implementation and test report](docs/IMPLEMENTATION_REPORT.md) and
[remaining blockers](HANDOFF_BLOCKERS.md). The complete two-provider vision
experiment, live end-to-end provider test, macOS run and final companion visual
review remain open. Measured lighting remains the default; no image generator is used.

## Requirements

- Blender **5.x or newer**. Tested here on Windows / Blender **5.3.0** only.
- Your own signed-in, unmodified Claude Code or Codex CLI. API-key environment
  overrides are removed from both child processes; no provider tokens are read or stored.
- Windows or macOS implementation paths; macOS is not yet verified.
- Codex privacy limitation: read-only write protection is not a verified
  reference-folder-only read boundary. See B-001 before using sensitive references.

## Install

1. Download `claude2blender-0.7.0.zip` from `dist/` in this fork.
2. In Blender open **Edit → Preferences → Add-ons → Install from Disk…**.
3. Choose the ZIP and enable Claude2Blender; press **N → Claude** in the viewport.
4. Select a backend and, if needed, set its CLI path in add-on preferences.
5. Use **Studio board → Open companion**, then **Copy pairing key** and paste it
   into the local page. Each Blender session gets a separate loopback port/key.

To update, install a newer ZIP and restart Blender. The package contains no texture
packs or HDRIs. Existing asset folders remain external.

## Studio workflow

1. Select a product, choose Material / Environment / Composition, and chat.
2. Inspect the returned code and use Preview / Apply; undo through History.
3. Add a part note or click a surface with Pin. In the companion, **Ask agent**
   sends an individual note; its resulting proposal remains reviewable in Blender.
4. Add shots from a scene camera, edit numbered ranges/motion in the companion,
   then approve the saved storyboard in Blender. Editing it invalidates approval.
5. Render the approved board. Select the product meshes first for QA masking.
6. Review each captured shot. Original returns to the rendered frame; Finish
   previews a linear light-group rebalance with an **approximate sRGB** display.
   Stage Finish, inspect it in Blender, Apply and rerender for final color.
7. **Ask agent to review this render** sends the captured frame, references and
   measured rubric; limited to three requests per capture. Corrections never auto-apply.
8. Measure QA and record visual review of dimensions, edges, materials, noise,
   scene fit and motion. Only then can Create Pack export frames, JPEG stills,
   contact sheet, MP4 when available, and a manifest with frame hashes.

Render notes retain before/after capture links. A note is marked done by the user;
applying code alone is not proof the visual issue was solved. Keep the `.c2b` folder
with its project. Save As carries JSON metadata; old captured-render paths are
rejected in the new project, so rerender before Finish or Pack there. Paths containing
`#` must be renamed before rendering because Blender treats it as a frame placeholder.

## One-time Claude Code setup

1. Install Claude Code (full instructions: https://code.claude.com/docs/en/setup).
   * macOS / Linux, in Terminal: `curl -fsSL https://claude.ai/install.sh | bash`
   * Windows, in PowerShell: `irm https://claude.ai/install.ps1 | iex`
2. Open a new terminal, run `claude`, type `/login` and sign in with your
   Claude account. You can close it afterwards.
3. In Blender, go to **Preferences → Add-ons → Claude2Blender** and press
   **Check Claude Code**. It should say it found Claude Code and that you're
   signed in. If Blender can't find it, paste the path from `which claude`
   (macOS/Linux) or `where claude` (Windows) into **Claude Code CLI** there.

The copy of Claude Code that ships inside the Claude Desktop app can't be used;
install the command-line version as above.

### Try it

1. Add a cube (or open any scene), select an object.
2. In the **Claude** tab, leave the mode on **Material**, type
   `brushed copper` and press **Generate with Claude**.
3. When the card says *Staged for review*, press **Preview** to see it, then
   **Apply**. Press **Undo** in History to take it back.

---

## Using it

1. **Open the panel.** Press **N** in the 3D viewport and choose the **Claude**
   tab. (If you also use the optional Blender MCP add-on with Claude Desktop, its
   connection status shows at the top. See *Claude Desktop fallback* below.)
2. **Mode.** *Material*, *Environment* or *Composition* Match. The mode tells
   Claude what kind of change you want and what it must leave alone. In
   Environment and Composition, an **Allowed** line under the mode shows what
   Claude may change. Click it to open the toggles (see below).
3. **Prompt.** Type in the field, or press the pencil for a wider editor.
4. **Selection.** Select objects in Object Mode, or press **Tab** and select faces
   to target a region of a mesh. The panel shows what will be sent.
5. **References.** Press **Add Images** (or drop images onto the sidebar in
   Blender 4.1+). Set each image's role (Material, Environment, Composition,
   Product) and add an optional note. Thumbnails are kept outside your `.blend`.
6. **Preserve Geometry** is on by default. See below.
7. **Generate with Claude.** Claude gets your prompt, the mode, the selected
   objects (dimensions, transforms, materials), any selected faces, a short list
   of the other objects in the scene, recent History, and your reference images.
   The status box goes through *Connecting*, *Processing* (for example "Looking
   at brushed.png…"), then *Completed* or *Failed*. Blender stays usable the
   whole time, and **Cancel** stops the request. When it finishes, a compact
   card shows the operation, the target object, the time taken and whether the
   change is *Staged for review*, *Applied*, *Undone* or *Discarded*, with
   **Review Code** and **Apply** buttons. Claude's explanation is folded
   under **Details**. Errors, and questions Claude needs you to answer, always
   stay visible.
   * **Follow-ups:** after the first result the button becomes **Refine with
     Claude**. Type what to change ("a bit darker", "only the top face") and
     press it again. Claude continues the same conversation. Turn off **Continue
     conversation**, or press **+**, to start fresh.
   * **Fallback (optional):** **Copy for Claude Desktop** copies a message to
     paste into Claude Desktop, for people who use the Blender MCP add-on.
8. **Review & Apply.** Claude stages its change in the panel instead of running
   it. **Preview** shows it on the real object (see below), **Review Code**
   shows the Python, then **Apply** or **Discard**.
9. **Undo / Redo / History.** Every Apply goes into **History** (last 10). See below.

### Visual material matching

1. Select the target. In **Object Mode** the selected objects get the material.
   In **Edit Mode** (face select) only the selected faces get it, and every other
   face keeps its slot and material.
2. In **References**, press **Add Images** (or drop photos on the sidebar). Leave
   the role as *Material* and add a note if useful ("ignore the colour, match
   the finish").
3. Mode **Material**, a short prompt ("Recreate this for a product render"),
   then **Generate with Claude**.

Claude receives the photo itself, not just its name. It analyses colour
(compensating for lighting), roughness and how it varies, metallic vs
dielectric, specular, coat, anisotropy, grain/bump scale and visible pattern.
It then builds a Principled BSDF material with procedural detail sized to your
part. Since CAD meshes often have no usable UVs, it uses Object/Generated
coordinates, and the photo is only used as a box-projected image texture when
a pattern can't be made procedurally. Large photos are downsized to 2048 px, and
EXR/HDR/TIFF/TGA/BMP files are converted, in a separate background Blender
process, so the interface doesn't freeze.

The completion card shows a colour swatch, the material name, roughness and
metallic, and a one-line surface description. When a procedural material can't
reproduce the photo exactly (a specific wood figure, a print, a logo), the card
says **Needs texture maps for an exact match** or **Approximate match** and why.
That warning stays visible. Claude's full technical notes are under
**Details**.

**Refining:** type a follow-up such as "make the surface more matte", "reduce
the grain size by 50%", "make the black slightly warmer, keep everything else"
or "match the reference more closely", then press **Refine with Claude**. Claude
gets the current node tree of the target's material and your reference images
again, changes only what you asked, and keeps the material's name.

**How targeting stays exact:** Claude's code doesn't assign materials itself. It
calls `assign_material(mat)`, which the add-on provides:
* Face targets: the material is added as a slot if needed, and only the selected
  faces point at it. A mesh with no materials first gets an empty slot 0, so
  unselected faces keep "no material".
* Object targets: the selected objects' slots get the material. If an object
  shares its mesh with unselected objects (linked duplicates), it gets an
  object-level override so the others don't change.
* Face targets on a mesh shared by linked duplicates can't be isolated, because
  the faces are the same data. The panel warns you when that happens.

### Studio presets

In Material mode, pick a preset from the dropdown under the mode (white dry-blast ABS, soft-touch
black, vulcanized black, TPE, dot-grid rubber, brushed steel, scuffed copper, clear resin, PCB, glass,
aluminium and more) and press **Use Preset**. No Claude call is made; the change is staged so you can
Preview, Apply and Undo it like any other. Claude can also start from a preset
(`preset_material("soft_touch_black")`) when your prompt matches one.

Presets use texture packs when they are installed: set **Texture Library** in the add-on preferences
to the folder holding them (for example `worn-old-plastic-bl`, `Copper-scuffed_bl` or Poliigon folders,
up to two levels deep). The preferences list which packs were found. Without a pack, the preset uses
procedural grain.

### Studio styles

In Environment mode, pick **Dark studio**, **High-key white** or **Colour gradient** from the dropdown
and press **Use Style**. These are Blender Director's tuned looks: lights placed around your product
relative to the scene camera and sized from the product (same look at any scale), a studio world, a
floor or sweep, and for Colour gradient a glowing orange-to-red wall. No Claude call is made. Like any
change it is staged for Preview / Apply / Undo and checked against Allowed Changes. Switching styles
reuses the same lights and hides the ones the new look doesn't use; your own lights are never changed.
Claude can start from them too (`c2b.studio_style("dark")`). Sample renders: `tests/real_results/style_*.png`.

### Measured lighting match

In Environment mode, add a reference photo and press **Measure Lighting from Reference**. Instead of
estimating, it measures:

1. A background Blender renders a temporary copy of your scene through your camera under 25 soft test
   lights (3 rings of 8 plus overhead) and a neutral world, each in its own light group. Your file is not
   changed and Blender stays usable; the panel shows progress and a cancel button.
2. A least-squares fit finds how strong and what colour each test light must be to reproduce the
   photo's shading pattern on your product, its rims and the background.
3. The lights that matter are staged as real area lights (`C2B Match L07`, ...) plus a studio world,
   for Preview / Apply / Undo. Exposure is folded into the light energies, so your colour management
   is untouched. The summary names the strongest light directions and the fit residuals (lower is
   closer; no match percentage is claimed). Claude refines these lights by name in follow-ups.

Limits: it matches light direction, balance and colour, not the camera angle, props or backdrop
shape. Lights come from a fixed 25-light dome, so a key between two rings is split between them and
tends to land in the lower one. A reference with a very busy or uneven background may not separate
cleanly from the product. Your own lights stay on (they aren't part of the fit), so switch them off
for a true comparison. Test and side-by-side: `tests/test_refmatch.py`,
`tests/real_results/refmatch_reference.png` vs `refmatch_matched.png`.

### Environment matching

1. Mode **Environment**. Add a reference photo (role *Environment*).
2. Check **Allowed** under the mode. By default Lighting, World and Backdrop are
   on, and Camera, object Positions/Rotations/Spacing and Output are off, so
   your product and camera stay exactly where they are.
3. Prompt, for example "Match the lighting and background of this photo", then
   **Generate with Claude**.

Claude looks at the photo and works out the key light direction and how soft it
is (from shadow edges), fill and rim lights and their ratios, shadow density,
the background colours or gradient, whether there is a visible floor or sweep,
brightness and contrast, the shape of reflections (softboxes, strip lights) and
atmosphere. It then builds that with real elements, through helper functions
the add-on provides:

* **Lights** (`C2B Key`, `C2B Fill`, `C2B Rim`, …): area, spot, point or sun
  lights aimed at your product. Their size and distance are set from your
  product's real dimensions.
* **World** (`C2B Studio World`): a procedural gradient. The background the
  camera sees can differ from the light the world adds. Your own world is kept,
  and Undo brings it back.
* **Backdrop** (`C2B Backdrop`): an infinity-cove sweep or floor under the
  product, with a matte material.
* **Exposure and contrast**: view transform, look and exposure. Output
  resolution and the render engine stay as they are unless you allow Output.

Everything new goes into a **Claude2Blender Studio** collection. Refinements
look things up by name and update them, so asking for "softer shadows" five
times never gives you five key lights. Nothing is ever deleted: a light the new
look doesn't need is hidden instead.

It works with EEVEE and Cycles. Softness comes from light size, not engine
tricks, and the engine isn't switched. When an exact match would need the
original HDRI or a photographed backdrop, Claude builds the closest procedural
version, and the card says **Needs an HDRI or textures to match exactly** and
why.

The completion card lists one line each for lighting, world, backdrop, camera,
objects and render, for example "Large soft key upper left, 3:1 fill, cool rim".

### Composition matching

1. Mode **Composition**. Add a reference (role *Composition* or *Product*).
2. **Select the parts that may move.** By default only selected objects may move;
   turn on **Full assembly** to let Claude arrange everything. Lighting is off
   by default in this mode.
3. Prompt, for example "Recreate the camera angle and exploded arrangement".

Claude reads the camera elevation and side, perspective (which tells it the
focal length), framing, the product's orientation and, for exploded views, the
axis, order and gaps. It identifies the parts in the photo with your objects by
name, size and position, and arranges **your existing objects**. It never adds
replacement objects. It adjusts your scene camera (or creates `C2B Camera` if
there is none) and frames the parts for your current output aspect.

Positions are estimates from one image. Refine them with follow-ups: "increase
the spacing between the exploded components", "rotate the camera slightly to
the left", "match the reference camera angle more closely".

**Parented parts:** moves are made in world space through the parent's matrix.
Only location and rotation are written, never scale, parenting or the parent
inverse, so a child (a screw on a lid) moves rigidly with its parent and nothing
is distorted. The change summary says when children follow their parent.
Re-parenting is always blocked.

### Allowed changes

| Toggle | What Claude may do | Environment | Composition |
| --- | --- | --- | --- |
| Lighting | create/adjust lights, exposure, contrast, engine light settings | on | off |
| World | world background and lighting, transparent film | on | off |
| Backdrop | create or resize a backdrop/floor and its material | on | off |
| Camera | move the camera, lens, depth of field, active camera | off | on |
| Positions | move the movable objects as a group | off | on |
| Rotations | rotate the movable objects | off | on |
| Spacing | change distances between movable objects (exploded views) | off | on |
| Output | render engine and output resolution | off | off |
| Full assembly | any object may move, not only the selection | off | off |

Positions and Spacing are separate on purpose. With Positions on and Spacing off,
the parts may only move together. With Spacing on and Positions off, they may
spread apart but the group keeps its centre.

After Claude's code runs (Preview or Apply), the add-on compares the scene with
how it was before. If anything changed outside the toggles, the whole change is
taken back on the spot and the panel says what was blocked, for example
"Camera is off: changed camera settings of Camera". The proposal stays staged,
so you can allow it or ask Claude for another version. These are always blocked
in both modes: deleting anything, re-parenting, adding constraints, hiding your
objects, changing their materials (use Material mode), and moving objects that
aren't movable. Preserve Geometry still guards meshes, UVs, scale and modifiers.

### Preview

**Preview** runs the staged change on your real scene, records exactly what it
touched, and switches the viewport so you can judge it:

* Material: Solid viewports switch to Material Preview.
* Environment: Material Preview using the scene's own lights and world, so the
  new lighting shows in real time (EEVEE in the viewport, whatever engine you
  render with).
* Composition: the viewport looks through the scene camera.

Your viewport settings come back when the preview ends. While previewing:

* **Original / Proposed** flips the scene between before and after, exactly, so
  you can compare. Nothing is re-run.
* **Changes in this preview** lists the lights created or modified, camera
  changes, world changes, objects moved or rotated, children that follow their
  parent, render settings, and the geometry protection status.

It is not committed:

* **Apply** keeps the proposed change and adds it to History, without running
  the code again (even if you were looking at Original).
* **End Preview** or **Discard** reverts exactly what the preview changed and
  removes the materials it created. End Preview keeps the change staged.
* **Saving while previewing** writes the file without the preview. The add-on
  takes the preview out just before the save and puts it back right after.
* A new Generate result, Undo/Redo or Ctrl+Z ends the preview first.

Because Preview runs Claude's code, it only happens when you press it, and
Preserve Geometry guards it the same way as Apply.

### Undo, Redo and History

Works like a design app's history panel, without going back to Claude:

* **Undo** reverts the newest applied change. Its code and result are kept.
* **Redo** puts the next undone change back exactly as it was. Claude's code is
  not run again, so nothing is duplicated.
* **Go to This Version** (select a row in History) steps back or forward to
  that version; **Original** goes back to before the first change.
* **Apply Again** runs a stored change's code again as a new change, e.g. after
  you applied something else on top, or on an entry from an abandoned branch.
* **Load into Review** puts a stored change back into Review & Apply so you can
  read it, or ask Claude to tweak it.

As in design apps, applying a new change after an Undo ends the redo branch.
Those entries stay in the list (marked with a script icon) and can still be
used with **Apply Again**.

**Only what a change touched is reverted.** Each Apply records before/after
values for exactly the things it changed: material slots and per-face material
assignments, materials and worlds edited in place (a hidden backup copy is
swapped in and out, so node trees come back exactly and keep their names),
object position/rotation/scale/visibility/parenting (exact values, not
rounded), light and camera settings including depth of field, the scene's world,
active camera, colour management, render engine, resolution and EEVEE/Cycles
settings, and objects it created (lights, cameras, backdrops, collections:
hidden on Undo, brought back on Redo). So Undo, Redo, Go to Version and Apply
Again work for whole environment and composition changes too. Other objects, and edits you made by hand afterwards,
are left alone. With Preserve Geometry off, mesh edits are recorded too.

**Blender's own Ctrl+Z still works.** Apply, Undo, Redo and Go To are normal
undo steps, and after any Ctrl+Z / Shift+Ctrl+Z the History re-checks which
changes are in effect. If Ctrl+Z goes back past an Apply, that entry can't be
redone from History any more, but Apply Again still works.

**Clear History** forgets the list and deletes the hidden backups; the scene
stays as it is. History is per session and resets when you open another file.
Hidden backups are named `.c2b~…`. They are left out whenever you save, so your
.blend never contains them.

### Preserve Geometry

When on, every Apply and Preview is checked against a snapshot taken just before
it runs. If the change edits mesh data (vertices, edges, faces) or UV maps,
changes an object's scale,
adds/removes/toggles a modifier, or removes or renames an existing object, the
Apply is rolled back automatically and the proposal stays in the panel so you
can discard it or ask Claude for another version. Moving and rotating objects is
allowed (Composition Match needs it for poses and exploded views), and so are
new materials, lights, cameras and world settings.

Turn it off only when you want Claude to model.

### What stays untouched

* The panel's state (prompt, references, staged change) lives in Blender's
  window manager, which is not saved into `.blend` files. Opening the panel or
  sending a request never modifies your project.
* Only **Apply** commits a change, and only after you press it. **Preview** is
  temporary and is never saved into the file.
* The last request is also written to Blender's config folder as
  `claude2blender/last_request.json` for debugging.

---

## How generation works

`backends.py` owns provider commands, event parsing, sign-in probes, cancellation
and error classification. Both adapters return one recursively strict schema.
The add-on records the conversation and sends a bounded recent context each turn;
it never depends on a provider's session resume. Latency and available usage data
are recorded per assistant turn. Quota errors offer an explicit backend switch.

Claude reads the supplied image paths. Codex receives attached images and stdin,
with read-only execution, user configuration disabled and a strict schema file.
Only the addon-owned MCP shim is configured when the companion is active; the shim
cannot apply code. Code is syntax-checked and staged through the existing bridge.
Generated responses are discarded when the request, project or captured scene
signature changes while waiting. The signature covers transforms, selection,
material inputs, cameras and light energy, not every possible Blender datablock edit.

The process uses a user-data workspace, strips provider API-key overrides and
honors Blender Online Access for provider calls. Reference conversions use copies.
No Agent SDK or provider credential storage is used. CLI sign-in remains the user's
own normal sign-in process. See [step 1 evidence](docs/STEP1_VERIFICATION.md) for
verified Codex flags and the unresolved filesystem-isolation probe.

## Claude Desktop fallback (optional)

You don't need this for Generate with Claude. It's for people who already use
the community [Blender MCP](https://github.com/ahujasid/blender-mcp) add-on with
Claude Desktop: press **Copy for Claude Desktop**, paste into Claude Desktop, and
Claude reads the request and stages its change in the same Review & Apply panel.

The Blender MCP has two halves:

```
Claude Desktop ──MCP (stdio)──▶ blender-mcp server (uvx blender-mcp, src/blender_mcp/server.py)
                                     │  JSON over TCP, localhost:9876
                                     ▼
                            MCP for Blender add-on (addon.py) inside Blender
                              • socket thread receives {"type": ..., "params": ...}
                              • queues it; a bpy timer runs it on Blender's main thread
                              • handlers: get_scene_info, get_object_info,
                                get_viewport_screenshot, execute_code, Poly Haven, …
```

Claude2Blender does not open a second socket. It registers a small API object at
`bpy.app.driver_namespace["claude2blender"]`, which Claude reaches with the
MCP's existing `execute_blender_code` tool:

| Call | Purpose |
| --- | --- |
| `get_request()` | The request you last sent: prompt, mode and its guidance, Preserve Geometry rule, selected objects (dimensions, transforms, materials), edit-mode faces per object as compact index ranges, reference image paths, roles and notes, scene units/engine. |
| `live_context()` | The same, built from the current state without pressing Send. |
| `stage_proposal(code, summary)` | Puts Python code in the Review & Apply panel. Syntax is checked immediately. |
| `proposal_status()` | Whether the user applied, discarded or rolled back the change. |
| `expand_indices("0-3,7")` | Turns face strings into lists. |
| `helpers_help()` | Documentation of the `c2b` scene helpers. |
| `scene_layout()` | World-space layout of objects, lights, cameras, world and render settings. |

Staged code runs in Object Mode with `bpy`, `request`, `expand_indices`,
`assign_material` and `c2b` (scene helpers) available. In Environment and
Composition the request includes `permissions` and `scene.layout`.

### Files

```
Claude4Blender/
├── claude2blender/           the add-on (install this)
│   ├── __init__.py           bl_info, registration
│   ├── blender_manifest.toml extension manifest for Blender 5.x+
│   ├── properties.py         modes, reference roles, panel state
│   ├── claude_cli.py         Generate with Claude: background `claude -p`, status, follow-ups, prefs
│   ├── bridge.py             request building, selection/face capture, API for Claude, MCP status
│   ├── history.py            change history: targeted undo/redo, live preview, Ctrl+Z and save handling
│   ├── materials.py          assign_material (exact object/face targeting), material descriptions
│   ├── scene_tools.py        c2b helpers: lights, camera, backdrop, studio world, parent-safe place/explode/frame
│   ├── guard.py              Allowed Changes: checks what an environment/composition change touched
│   ├── operators.py          send, references, review/apply, history ops, Preserve Geometry guard
│   ├── references.py         thumbnail previews
│   └── ui.py                 sidebar panels
├── dist/claude2blender-0.7.0.zip   ready-to-install zip
├── tests/                    headless tests (no user files opened)
└── build_zip.sh
```

### Tests

```
pip install bpy            # or use Blender itself
python tests/test_headless.py
python tests/test_panels_draw.py
python tests/test_history.py
python tests/test_generate.py            # stand-in CLI; C2B_REAL_CLAUDE=1 adds a real run
python tests/test_materials.py           # faces/objects, preview, saving, images; C2B_REAL_CLAUDE=1 adds
                                         # a real run on a rendered copper photo
python tests/test_scene.py               # v0.5 sample scenes: lighting, camera angle, exploded view,
                                         # refinements, undo/redo, Allowed Changes, Original/Proposed
python tests/test_presets.py             # studio material presets, texture packs, Use Preset
python tests/test_styles.py              # studio styles; C2B_STYLE_RENDERS=<dir> renders each style
python tests/test_refmatch.py            # measured lighting match on a rendered reference (C2B_GPU=1)
# The stand-in CLI (tests/fake_cli.py) is a shebang script on macOS/Linux and an npm-style
# claude.cmd shim on Windows, so the same tests run on both.
C2B_REAL_CLAUDE=1 python tests/test_scene_real.py   # real Claude on rendered environment and
                                                    # composition references, with follow-ups
                                                    # (renders from the last run: tests/real_results/)
# with Blender:
blender --background --factory-startup --python tests/test_headless.py
```

---

## Known limits

* This is an early version. The automated tests run in headless Blender; a few
  safety features (notably the automatic rollback of a blocked change) have
  been checked there but not yet clicked through in every Blender version.

* Claude doesn't see the viewport during Generate, only the scene description
  and your reference images. It can't compare its result to the photo
  visually; a rendered before/after comparison is the natural next step.
* Material matching is a best estimate from one photo. Lighting in the photo
  affects perceived colour and gloss, and exact patterns need scanned or PBR
  texture maps (the card says when).
* Preview needs the change to be recordable (materials, slots, face assignments,
  transforms, lights, world). If a change can't be reverted from the record, End
  Preview tells you to use Ctrl+Z.
* With the Claude Desktop fallback, Claude sees reference images only if you
  also attach them there.
* The prompt field is single-line (the pencil opens a wider editor).
* Preserve Geometry guards meshes. It does not inspect modifier settings, curves
  or other non-mesh data.
* Panel state and History reset when Blender restarts or another file is opened.
* History doesn't record modifier settings, curve edits, compositor nodes or
  deleted objects. A change that deletes objects can only be reverted with
  Ctrl+Z (and Allowed Changes blocks deletion in Environment and Composition).
* Environment and Composition matches are estimates from a single image. Light
  intensities in particular depend on the photo's exposure, so expect to refine
  with a follow-up. Claude doesn't see its own render to self-correct.
* The comparison is Original/Proposed in the live viewport, not a separate
  rendered image side by side. That kept it exact and safe; rendered thumbnails
  are on the roadmap.
* A blocked change is taken back at once from the change record. If it also
  touched something the record can't restore (constraints, deletions), the
  add-on falls back to Blender's own undo after Apply (see the next point).
* The automatic rollback uses Blender's own undo after Apply finishes; it can't run
  in headless tests, so confirm it in the live UI (Ctrl+Z is always the fallback).

## Roadmap

* Render a small before/after comparison next to the reference image, and let
  Claude see it to self-correct (lighting intensity especially).
* HDRI library lookup for environment references that need a real HDRI.
* PBR texture-map sets (albedo/roughness/normal) from a scan folder.
