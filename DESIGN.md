# Companion implementation record

Surface: `claude2blender/companion.html`. Mode: Operate.

Preserve the incumbent dark Blender-like control surface: system font, warm-white
text, neutral charcoal backgrounds, amber primary actions, visible field labels
and focus rings. Wide view uses storyboard/render work on the left and part notes
and conversation on the right. At 800px it becomes one column. Storyboard shot
numbers are ordinary integers. Render imagery carries the visual content.

No external UI dependencies. User/provider text enters through textContent,
never HTML. Pairing key stays in page memory; it is cleared from the input after
pairing. Review/apply authority stays in Blender. Loading identities prevent
stale rendered images from being annotated as a different shot; storyboard drafts
survive unrelated refreshes and edits during save.

Verification: paired board and note save visually checked at desktop and 390px;
new review controls syntax-checked and source-reviewed. The independent finish
review disposition is **recapture**: expanded Review/Finish/QA/Pack screenshots
are still missing. This file records the built system, not visual certification.
