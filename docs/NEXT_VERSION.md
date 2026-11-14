# Next version (0.8.0) requests

Logged November 14, 2026, after testing 0.7.0 in Blender 5.3. Not started.

## 1. Choose the model from the UI

**Today:** the model is a free-text field per backend (`Claude model`, `Codex model`) in the add-on's
Preferences. It is passed to the CLI's `--model` flag. An empty field uses the CLI default. A bad name only
fails when a message is sent.

**Wanted:** pick the model without opening Preferences, in the Claude tab panel and on the companion page.

- A dropdown next to the Backend switch, listing the models for the selected backend.
- Keep a "Custom..." option so a new model name still works without an add-on update.
- Show the active backend and model on each chat turn so it is clear what answered.
- Validate the name before sending, or show a clear message when the CLI rejects it.
- Remember the choice per backend. Switching backend (including the usage-limit fallback) should switch to
  that backend's saved model.

## 2. Paste images in as references

**Today:** references are added with the Add Images button or by dropping files on the sidebar.

**Wanted:** copy an image anywhere (screenshot, browser, Photoshop) and paste it straight in as a reference.

- A **Paste image** button in the References section of the panel that reads the clipboard.
- Ctrl+V on the companion page, and on the chat box there, attaches the pasted image.
- Save the pasted image into the project's sidecar folder with a generated name so it survives the clipboard
  changing.
- Treat it like any other reference from then on (thumbnail, remove, sent to the agent, used by the
  measured lighting match).

**Open questions for the builder:** whether Blender's Python API can read an image from the system clipboard on
Windows without a new dependency (it likely cannot natively; check `bpy` and `wm.paste` first, otherwise
use the companion page, where the browser can read pasted images). Report what works before building.

## 3. Pick more than one mode at once

**Today:** Mode is a single choice (Material, Environment, Composition, and so on). A request that spans
more than one, for example a new material and new lighting, has to be split into separate runs.

**Wanted:** the modes become toggles, so any combination can be on for one request.

- Replace the single Mode selector with on/off toggles (multi-select), with at least one always on.
- The request sent to the agent lists every selected mode, and the agent may change only those areas.
- The Allowed Changes guard and Preserve Geometry must follow the combined set. Each selected mode adds its
  permissions, nothing else.
- Review & Apply and History treat the result as one change, so one Apply and one undo cover all of it.
- Keep the old single-mode behaviour as the default so existing presets and saved requests still work.

## 4. Reference image with a note: Enter doesn't send

**Today:** after adding a reference image with a note, pressing Enter does not submit it. The user was not sure
whether Generate with Claude has to be clicked afterwards, which is not obvious from the panel.

**Wanted:** it should be clear and quick to send.

- Decide the intended flow and show it: note typed, then Enter (or a Send button) sends the request with the
  reference attached.
- If Enter only confirms the text field (Blender's default), say so in the field's hint text and add a visible
  **Send** button beside the note so nobody has to look for Generate with Claude.
- Confirm the note and the image actually travel together in the request, and show a small "1 image, 1 note"
  line before sending.

**To verify first:** reproduce it in Blender and record exactly what Enter does in that field.
