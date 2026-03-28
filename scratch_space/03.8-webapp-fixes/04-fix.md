# Various fixes

## e1 - Voice page: no stop button + 422 on convert

### Root cause analysis

**Bug A - No stop button**

The record button uses a **hold-to-record** model: `mousedown` starts recording,
`mouseup` / `mouseleave` / `touchend` stops it. There is no separate stop button.

Problems with this design:
- `mouseleave` fires if the user drifts off the button while holding, stopping recording unexpectedly
- A normal click (mousedown + immediate mouseup) produces a clip of near-zero duration
- On touch devices, a tap triggers both `touchstart` and `touchend` almost simultaneously, again producing an empty clip
- The help text "Click to record a clip. Release to transcribe." is ambiguous; the status
  message after session start says "Click 'Record clip' and speak" (no mention of holding)

**Bug B - 422 on "Convert to recipe"**

The backend raises HTTP 422 when `recipe_note.notes` is empty:

```python
if not recipe_note.notes:
    raise HTTPException(status_code=422, detail="Voice session has no notes to convert.")
```

This triggers because Bug A causes audio clips to be near-empty or the upload fails silently,
so no note is ever appended. The JS catches the 422 but only shows the generic message
"Error: Conversion failed" - the user has no idea why.

The "Freeze session" button does not check whether any notes exist before allowing freeze,
so the whole "freeze → convert" path can be attempted on an empty session.

---

### Fix plan

**1. Switch record button to click-to-toggle (`static/js/voice.js`)**

Remove all `mousedown` / `mouseup` / `mouseleave` / `touchstart` / `touchend` listeners
on `#btn-record`. Replace with a single `click` listener that toggles between
`startRecording()` and `stopRecording()`.

When recording is active:
- Change button label to "Stop recording"
- Change button class from `is-danger` to `is-warning` (or add a pulsing style)
- Keep the existing timer display

When recording stops:
- Restore label to "Record clip" and class to `is-danger`

This makes the UX self-explanatory and eliminates the accidental-stop-on-mouseleave problem.

**2. Add a dedicated "Stop" button as an alternative (`templates/pages/voice.html`)**

Add a second `<button id="btn-stop" class="button is-warning is-hidden">Stop recording</button>`
next to `#btn-record`. Show it (and hide the record button) when recording starts;
swap back on stop. This keeps the two actions visually distinct and mirrors how most
recording UIs work. This pairs with change 1 - both can be done together.

**3. Guard "Freeze" against empty session (`static/js/voice.js`)**

Track a local `noteCount` counter. Increment it in `appendNote()`. Before the freeze
fetch, check `noteCount === 0` and show a warning in `#action-status` instead of
proceeding. This prevents the user from freezing an empty session and hitting the 422.

**4. Surface the 422 detail to the user (`static/js/voice.js`)**

In the `btnToRecipe` click handler, parse the JSON error body on non-ok responses and
show `data.detail` in `#action-status` instead of the generic "Conversion failed" string.
Pattern:

```js
if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail ?? "Conversion failed");
}
```

**5. Guard "Freeze" / "Convert" buttons in the backend (optional, low priority)**

The backend already returns 422 for empty sessions - that is correct defensive behaviour.
No change needed on the server side. The frontend fixes above are sufficient.

---

### Files to change

| File | Changes |
|---|---|
| `static/js/voice.js` | Switch to click-to-toggle (fix 1), add note counter guard (fix 3), improve error message (fix 4) |
| `templates/pages/voice.html` | Add `#btn-stop` button element (fix 2) |

No backend changes required.
