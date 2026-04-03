(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────
  let sessionId = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let timerInterval = null;
  let timerSeconds = 0;
  let noteCount = 0;

  // ── DOM shortcuts ──────────────────────────────────────────
  const $ = id => document.getElementById(id);
  const stepStart  = $("step-start");
  const stepRecord = $("step-record");
  const btnStart   = $("btn-start-session");
  const btnRecord  = $("btn-record");
  const btnStop    = $("btn-stop");
  const btnRecordLabel = $("btn-record-label");
  const btnFreeze  = $("btn-freeze");
  const btnToRecipe = $("btn-to-recipe");
  const sessionTag = $("session-id-tag");
  const recordStatus = $("record-status");
  const recordTimer  = $("record-timer");
  const transcriptList = $("transcript-list");
  const transcriptEmpty = $("transcript-empty");
  const actionStatus = $("action-status");

  function csrfHeader() {
    const meta = document.querySelector("meta[name='csrf-token']");
    return meta ? { "X-CSRF-Token": meta.content } : {};
  }

  function appendNote(text, timestamp) {
    noteCount++;
    if (transcriptEmpty) transcriptEmpty.style.display = "none";
    const p = document.createElement("p");
    const ts = new Date(timestamp).toLocaleTimeString();
    p.innerHTML = `<strong class="has-text-grey-dark">${ts}</strong> &mdash; ${escHtml(text)}`;
    p.className = "mb-1 is-size-7";
    transcriptList.appendChild(p);
    transcriptList.scrollTop = transcriptList.scrollHeight;
  }

  function escHtml(text) {
    const d = document.createElement("div");
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
  }

  function setStatus(msg, el) {
    if (el) el.textContent = msg;
  }

  // ── Start session ──────────────────────────────────────────
  btnStart.addEventListener("click", async () => {
    btnStart.disabled = true;
    btnStart.classList.add("is-loading");
    try {
      const resp = await fetch("/api/v1/voice/create", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...csrfHeader() },
      });
      if (!resp.ok) { throw new Error("Failed to create session"); }
      const data = await resp.json();
      sessionId = data.session_id;
      sessionTag.textContent = sessionId;
      stepStart.classList.add("is-hidden");
      stepRecord.classList.remove("is-hidden");
      btnRecord.disabled = false;
      setStatus("Session ready. Click 'Record clip' to start recording.", recordStatus);
    } catch (err) {
      setStatus("Error: " + err.message, recordStatus);
      btnStart.disabled = false;
    } finally {
      btnStart.classList.remove("is-loading");
    }
  });

  // ── Record a clip ──────────────────────────────────────────
  btnRecord.addEventListener("click", startRecording);
  btnStop.addEventListener("click", stopRecording);

  async function startRecording() {
    if (isRecording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.start();
      isRecording = true;
      btnRecord.classList.add("is-hidden");
      btnStop.classList.remove("is-hidden");
      setStatus("Recording… speak now.", recordStatus);
      // Timer
      timerSeconds = 0;
      recordTimer.textContent = "0s";
      recordTimer.style.display = "";
      timerInterval = setInterval(() => {
        timerSeconds++;
        if (recordTimer) recordTimer.textContent = timerSeconds + "s";
      }, 1000);
    } catch (_) {
      setStatus("Microphone access denied.", recordStatus);
    }
  }

  async function stopRecording() {
    if (!isRecording || !mediaRecorder) return;
    clearInterval(timerInterval);
    if (recordTimer) recordTimer.style.display = "none";
    mediaRecorder.stop();
    isRecording = false;
    btnStop.classList.add("is-hidden");
    btnRecord.classList.remove("is-hidden");
    setStatus("Transcribing…", recordStatus);

    mediaRecorder.onstop = async () => {
      const blob = new Blob(audioChunks, { type: "audio/webm" });
      mediaRecorder.stream.getTracks().forEach(t => t.stop());
      mediaRecorder = null;
      await uploadClip(blob);
    };
  }

  async function uploadClip(blob) {
    const form = new FormData();
    form.append("audio", blob, "clip.webm");
    try {
      const resp = await fetch(`/api/v1/voice/${sessionId}/upload`, {
        method: "POST",
        headers: csrfHeader(),
        body: form,
      });
      if (!resp.ok) { throw new Error("Upload failed"); }
      const note = await resp.json();
      appendNote(note.text, note.timestamp);
      setStatus("Clip transcribed. Record another or freeze the session.", recordStatus);
    } catch (err) {
      setStatus("Transcription error: " + err.message, recordStatus);
    }
  }

  // ── Freeze session ─────────────────────────────────────────
  btnFreeze.addEventListener("click", async () => {
    if (noteCount === 0) {
      setStatus("Record at least one clip before freezing the session.", actionStatus);
      return;
    }
    btnFreeze.disabled = true;
    btnFreeze.classList.add("is-loading");
    try {
      const resp = await fetch(`/api/v1/voice/${sessionId}/freeze`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...csrfHeader() },
      });
      if (!resp.ok) { throw new Error("Freeze failed"); }
      btnRecord.disabled = true;
      btnFreeze.classList.add("is-hidden");
      btnToRecipe.classList.remove("is-hidden");
      setStatus("Session frozen. Click 'Convert to recipe' when ready.", actionStatus);
    } catch (err) {
      setStatus("Error: " + err.message, actionStatus);
      btnFreeze.disabled = false;
    } finally {
      btnFreeze.classList.remove("is-loading");
    }
  });

  // ── Convert to recipe ──────────────────────────────────────
  btnToRecipe.addEventListener("click", async () => {
    btnToRecipe.disabled = true;
    btnToRecipe.classList.add("is-loading");
    setStatus("Converting transcript to recipe…", actionStatus);
    try {
      const resp = await fetch(`/api/v1/voice/${sessionId}/to-recipe`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...csrfHeader() },
      });
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(errBody.detail ?? "Conversion failed");
      }
      const detail = await resp.json();
      // Navigate to the new recipe
      window.location.href = `/recipes/${detail.id}`;
    } catch (err) {
      setStatus("Error: " + err.message, actionStatus);
      btnToRecipe.disabled = false;
      btnToRecipe.classList.remove("is-loading");
    }
  });

  // ── Frozen sessions list ────────────────────────────────────
  const frozenList = $("frozen-sessions-list");
  const frozenEmpty = $("frozen-empty");

  async function loadFrozenSessions() {
    try {
      const resp = await fetch("/api/v1/voice/sessions/frozen", {
        headers: csrfHeader(),
      });
      if (!resp.ok) {
        setStatus("Failed to load frozen sessions", frozenEmpty);
        return;
      }
      const sessions = await resp.json();
      frozenList.innerHTML = "";
      if (sessions.length === 0) {
        frozenList.innerHTML = '<p class="has-text-grey is-size-7">No frozen sessions.</p>';
        return;
      }
      for (const s of sessions) {
        const noteCount = (s.note.notes || []).length;
        const startTime = s.note.start_time
          ? new Date(s.note.start_time).toLocaleString()
          : "Unknown";
        const box = document.createElement("div");
        box.className = "box mb-3";
        box.innerHTML = `
          <div class="is-flex is-justify-content-space-between is-align-items-center">
            <div>
              <p class="has-text-weight-semibold is-size-6">
                Session <span class="tag is-light">${escHtml(s.session_id)}</span>
              </p>
              <p class="is-size-7 has-text-grey">${startTime} &middot; ${noteCount} clip${noteCount !== 1 ? "s" : ""}</p>
            </div>
            <div class="buttons are-small">
              <button class="button is-info is-outlined" data-action="resume" data-sid="${escHtml(s.session_id)}">Resume</button>
              <button class="button is-success is-outlined" data-action="convert" data-sid="${escHtml(s.session_id)}">Convert</button>
              <button class="button is-danger is-outlined" data-action="delete" data-sid="${escHtml(s.session_id)}">Delete</button>
            </div>
          </div>`;
        frozenList.appendChild(box);
      }
    } catch (_) {
      frozenList.innerHTML = '<p class="has-text-grey is-size-7">Error loading frozen sessions.</p>';
    }
  }

  frozenList.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    const sid = btn.dataset.sid;
    btn.disabled = true;
    btn.classList.add("is-loading");

    try {
      if (action === "resume") {
        const resp = await fetch(`/api/v1/voice/${sid}/unfreeze`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader() },
        });
        if (!resp.ok) throw new Error("Unfreeze failed");
        // Switch the main UI to this session
        const data = await resp.json();
        sessionId = sid;
        sessionTag.textContent = sid;
        stepStart.classList.add("is-hidden");
        stepRecord.classList.remove("is-hidden");
        btnRecord.disabled = false;
        btnFreeze.disabled = false;
        btnFreeze.classList.remove("is-hidden");
        btnToRecipe.classList.add("is-hidden");
        // Populate existing transcript
        transcriptList.innerHTML = "";
        const notes = data.notes || [];
        noteCount = notes.length;
        if (noteCount > 0 && transcriptEmpty) transcriptEmpty.style.display = "none";
        for (const n of notes) {
          appendNote(n.text, n.timestamp);
        }
        setStatus("Session resumed. You can record more clips.", recordStatus);
        await loadFrozenSessions();

      } else if (action === "convert") {
        const resp = await fetch(`/api/v1/voice/${sid}/to-recipe`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader() },
        });
        if (!resp.ok) {
          const errBody = await resp.json().catch(() => ({}));
          throw new Error(errBody.detail ?? "Conversion failed");
        }
        const detail = await resp.json();
        window.location.href = `/recipes/${detail.id}`;

      } else if (action === "delete") {
        if (!confirm("Delete this session permanently?")) {
          btn.disabled = false;
          btn.classList.remove("is-loading");
          return;
        }
        const resp = await fetch(`/api/v1/voice/${sid}`, {
          method: "DELETE",
          headers: csrfHeader(),
        });
        if (!resp.ok) throw new Error("Delete failed");
        await loadFrozenSessions();
      }
    } catch (err) {
      setStatus("Error: " + err.message, actionStatus);
      btn.disabled = false;
      btn.classList.remove("is-loading");
    }
  });

  // Load frozen sessions on page load
  loadFrozenSessions();

})();
