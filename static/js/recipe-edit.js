(function () {
  "use strict";

  const recipeId = window.__recipeId;
  const dataEl = document.getElementById("recipe-data");
  if (!recipeId || !dataEl) return;

  let originalRecipe = JSON.parse(dataEl.textContent);
  let editMode = false;

  // ── DOM shortcuts ──────────────────────────────────────────
  const $ = id => document.getElementById(id);
  const btnToggle   = $("btn-toggle-edit");
  const toolbar     = $("edit-toolbar");
  const btnSave     = $("btn-save-edit");
  const btnCancel   = $("btn-cancel-edit");
  const saveStatus  = $("edit-save-status");
  const recipeName  = $("recipe-name");
  const mealCourse  = $("edit-meal-course");
  const prepsSection   = $("preparations-section");
  const notesSection   = $("notes-section");

  function csrfHeader() {
    const meta = document.querySelector("meta[name='csrf-token']");
    return meta ? { "X-CSRF-Token": meta.content } : {};
  }

  function escHtml(text) {
    const d = document.createElement("div");
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
  }

  // ── Enter edit mode ─────────────────────────────────────────
  function enterEditMode() {
    editMode = true;
    btnToggle.textContent = "Editing...";
    btnToggle.disabled = true;
    toolbar.classList.remove("is-hidden");

    // Make recipe name editable
    recipeName.contentEditable = "true";
    recipeName.classList.add("editable-field");

    // Make notes editable
    renderNotesEditable();

    // Make preparations editable
    prepsSection.querySelectorAll("[data-prep-idx]").forEach(renderPrepEditable);
  }

  // ── Exit edit mode ──────────────────────────────────────────
  function exitEditMode() {
    editMode = false;
    btnToggle.textContent = "Edit recipe";
    btnToggle.disabled = false;
    toolbar.classList.add("is-hidden");
    saveStatus.textContent = "";

    // Reload the page to reset to server state
    window.location.reload();
  }

  // ── Notes editing ───────────────────────────────────────────
  function renderNotesEditable() {
    const notes = originalRecipe.notes || [];
    let html = '<div class="box mb-4"><p class="title is-6 mb-2">Notes</p>';
    html += '<div id="edit-notes-list">';
    notes.forEach((note, i) => {
      html += `<div class="field has-addons mb-1" data-note-idx="${i}">
        <div class="control is-expanded">
          <input class="input is-small note-input" type="text" value="${escHtml(note)}">
        </div>
        <div class="control">
          <button class="button is-small is-danger is-light btn-remove-note" type="button">&times;</button>
        </div>
      </div>`;
    });
    html += '</div>';
    html += '<button class="button is-small is-light mt-2" id="btn-add-note" type="button">+ Add note</button>';
    html += '</div>';
    notesSection.innerHTML = html;

    $("btn-add-note").addEventListener("click", () => {
      const list = $("edit-notes-list");
      const idx = list.children.length;
      const div = document.createElement("div");
      div.className = "field has-addons mb-1";
      div.dataset.noteIdx = idx;
      div.innerHTML = `<div class="control is-expanded">
        <input class="input is-small note-input" type="text" value="" placeholder="New note">
      </div>
      <div class="control">
        <button class="button is-small is-danger is-light btn-remove-note" type="button">&times;</button>
      </div>`;
      list.appendChild(div);
    });

    notesSection.addEventListener("click", (e) => {
      if (e.target.classList.contains("btn-remove-note")) {
        e.target.closest("[data-note-idx]").remove();
      }
    });
  }

  // ── Preparation editing ─────────────────────────────────────
  function renderPrepEditable(prepDiv) {
    const prepIdx = parseInt(prepDiv.dataset.prepIdx, 10);
    const prep = originalRecipe.preparations[prepIdx];

    // Make prep name editable
    const nameEl = prepDiv.querySelector(".prep-name");
    if (nameEl) {
      nameEl.contentEditable = "true";
      nameEl.classList.add("editable-field");
    }

    // Replace ingredients table with editable form
    const ingTbody = prepDiv.querySelector(".ing-tbody");
    if (ingTbody) {
      let html = "";
      prep.ingredients.forEach((ing, i) => {
        html += `<tr data-ing-idx="${i}">
          <td><input class="input is-small ing-name-input" type="text" value="${escHtml(ing.name)}"></td>
          <td><input class="input is-small ing-qty-input" type="text" value="${escHtml(ing.quantity)}"></td>
          <td style="width:32px"><button class="button is-small is-danger is-light btn-remove-ing" type="button">&times;</button></td>
        </tr>`;
      });
      ingTbody.innerHTML = html;

      // Add "add ingredient" button
      const addBtn = document.createElement("button");
      addBtn.className = "button is-small is-light mt-2 btn-add-ing";
      addBtn.type = "button";
      addBtn.textContent = "+ Add ingredient";
      ingTbody.closest("table").after(addBtn);

      addBtn.addEventListener("click", () => {
        const tr = document.createElement("tr");
        tr.dataset.ingIdx = ingTbody.children.length;
        tr.innerHTML = `<td><input class="input is-small ing-name-input" type="text" value="" placeholder="Name"></td>
          <td><input class="input is-small ing-qty-input" type="text" value="" placeholder="Qty"></td>
          <td style="width:32px"><button class="button is-small is-danger is-light btn-remove-ing" type="button">&times;</button></td>`;
        ingTbody.appendChild(tr);
      });
    }

    // Replace steps list with editable form
    const stepsList = prepDiv.querySelector(".steps-list");
    if (stepsList) {
      let html = "";
      prep.steps.forEach((step, i) => {
        if (step.type === "text") {
          html += `<li class="mb-2" data-step-idx="${i}">
            <div class="field has-addons">
              <div class="control is-expanded">
                <input class="input is-small step-input" type="text" value="${escHtml(step.instruction || "")}">
              </div>
              <div class="control">
                <button class="button is-small is-danger is-light btn-remove-step" type="button">&times;</button>
              </div>
            </div>
          </li>`;
        } else {
          html += `<li class="mb-2" data-step-idx="${i}" data-step-type="image"><em class="has-text-grey">[image]</em></li>`;
        }
      });
      stepsList.innerHTML = html;

      // Add "add step" button
      const addStepBtn = document.createElement("button");
      addStepBtn.className = "button is-small is-light mt-2 btn-add-step";
      addStepBtn.type = "button";
      addStepBtn.textContent = "+ Add step";
      stepsList.after(addStepBtn);

      addStepBtn.addEventListener("click", () => {
        const li = document.createElement("li");
        li.className = "mb-2";
        li.dataset.stepIdx = stepsList.children.length;
        li.innerHTML = `<div class="field has-addons">
          <div class="control is-expanded">
            <input class="input is-small step-input" type="text" value="" placeholder="New step">
          </div>
          <div class="control">
            <button class="button is-small is-danger is-light btn-remove-step" type="button">&times;</button>
          </div>
        </div>`;
        stepsList.appendChild(li);
      });
    }
  }

  // ── Collect edited data ─────────────────────────────────────
  function collectRecipe() {
    const name = recipeName.textContent.trim();
    const mealCourseVal = mealCourse.value || null;

    // Notes
    const noteInputs = notesSection.querySelectorAll(".note-input");
    const notes = [];
    noteInputs.forEach(input => {
      const val = input.value.trim();
      if (val) notes.push(val);
    });

    // Preparations
    const preparations = [];
    prepsSection.querySelectorAll("[data-prep-idx]").forEach(prepDiv => {
      const nameEl = prepDiv.querySelector(".prep-name");
      let prepName = nameEl ? nameEl.textContent.trim() : null;
      // Clear auto-generated "Preparation N" names
      if (prepName && /^Preparation \d+$/.test(prepName)) prepName = null;

      const ingredients = [];
      prepDiv.querySelectorAll("[data-ing-idx]").forEach(tr => {
        const nameInput = tr.querySelector(".ing-name-input");
        const qtyInput = tr.querySelector(".ing-qty-input");
        if (nameInput && qtyInput) {
          const n = nameInput.value.trim();
          const q = qtyInput.value.trim();
          if (n) ingredients.push({ name: n, quantity: q });
        }
      });

      const steps = [];
      prepDiv.querySelectorAll("[data-step-idx]").forEach(li => {
        if (li.dataset.stepType === "image") {
          steps.push({ type: "image", instruction: null });
        } else {
          const input = li.querySelector(".step-input");
          if (input) {
            const text = input.value.trim();
            if (text) steps.push({ type: "text", instruction: text });
          }
        }
      });

      preparations.push({
        preparation_name: prepName,
        ingredients,
        steps,
      });
    });

    return {
      name,
      preparations,
      notes: notes.length > 0 ? notes : null,
      source: originalRecipe.source || null,
      meal_course: mealCourseVal,
    };
  }

  // ── Save ────────────────────────────────────────────────────
  async function saveRecipe() {
    const recipe = collectRecipe();
    btnSave.disabled = true;
    btnSave.classList.add("is-loading");
    saveStatus.textContent = "Saving...";
    try {
      const resp = await fetch(`/api/v1/recipes/${recipeId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify(recipe),
      });
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(errBody.detail ?? "Save failed");
      }
      // Refresh the page to show the updated recipe
      window.location.reload();
    } catch (err) {
      saveStatus.textContent = "Error: " + err.message;
      btnSave.disabled = false;
      btnSave.classList.remove("is-loading");
    }
  }

  // ── Event delegation for remove buttons ─────────────────────
  prepsSection.addEventListener("click", (e) => {
    if (e.target.classList.contains("btn-remove-ing")) {
      e.target.closest("tr").remove();
    }
    if (e.target.classList.contains("btn-remove-step")) {
      e.target.closest("li").remove();
    }
  });

  // ── Wire up buttons ─────────────────────────────────────────
  btnToggle.addEventListener("click", enterEditMode);
  btnSave.addEventListener("click", saveRecipe);
  btnCancel.addEventListener("click", exitEditMode);

})();
