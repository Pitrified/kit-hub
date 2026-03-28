(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────
  let sessionId = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let timerInterval = null;
  let timerSeconds = 0;

  // ── DOM shortcuts ──────────────────────────────────────────
  const $ = id => document.getElementById(id);
  const stepStart  = $("step-start");
  const stepRecord = $("step-record");
  const btnStart   = $("btn-start-session");
  const btnRecord  = $("btn-record");
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
      setStatus("Session ready. Click 'Record clip' and speak.", recordStatus);
    } catch (err) {
      setStatus("Error: " + err.message, recordStatus);
      btnStart.disabled = false;
    } finally {
      btnStart.classList.remove("is-loading");
    }
  });

  // ── Record a clip ──────────────────────────────────────────
  btnRecord.addEventListener("mousedown", startRecording);
  btnRecord.addEventListener("touchstart", e => { e.preventDefault(); startRecording(); });
  btnRecord.addEventListener("mouseup", stopRecording);
  btnRecord.addEventListener("mouseleave", stopRecording);
  btnRecord.addEventListener("touchend", e => { e.preventDefault(); stopRecording(); });

  async function startRecording() {
    if (isRecording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.start();
      isRecording = true;
      btnRecord.classList.add("is-loading");
      btnRecordLabel.textContent = "Recording… release to stop";
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
    btnRecord.classList.remove("is-loading");
    btnRecordLabel.textContent = "Record clip";
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
      if (!resp.ok) { throw new Error("Conversion failed"); }
      const detail = await resp.json();
      // Navigate to the new recipe
      window.location.href = `/recipes/${detail.id}`;
    } catch (err) {
      setStatus("Error: " + err.message, actionStatus);
      btnToRecipe.disabled = false;
      btnToRecipe.classList.remove("is-loading");
    }
  });

})();
