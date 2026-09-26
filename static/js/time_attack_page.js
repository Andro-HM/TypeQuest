import {
  createChunkStream,
  ensureStreamLength,
} from "./chunk_stream.js";
import {
  advanceTimeAttackTimer,
  createTimeAttackTimer,
  formatRemainingSeconds,
  getCountdownRemainingMs,
  getTimeAttackRemainingMs,
  pauseTimeAttackTimer,
  resumeTimeAttackTimer,
} from "./time_attack_timer.js";
import {
  calculateMetrics,
  countBufferMetrics,
  countCompletedTargetWords,
} from "./metrics.js";
import {
  backspaceTimeAttack,
  createTimeAttackState,
  getVisibleSlots,
  moveTimeAttackCursorLeft,
  moveTimeAttackCursorRight,
  typeTimeAttackCharacter,
  WINDOW_CHARACTERS,
} from "./time_attack.js";

const chunks = JSON.parse(document.getElementById("time-attack-chunks").textContent);
const typingArea = document.getElementById("time-attack-area");
const durationSeconds = Number(typingArea.dataset.durationSeconds);
const durationMs = durationSeconds * 1000;
const stream = createChunkStream(chunks);
const typingState = createTimeAttackState(stream.target);
const run = createTimeAttackTimer(durationMs, performance.now());
let transitionTimeoutId = null;

const status = document.getElementById("time-attack-status");
const pauseButton = document.getElementById("pause-button");
const resumeButton = document.getElementById("resume-button");
const timeRemaining = document.getElementById("time-remaining");
const rawWpm = document.getElementById("raw-wpm");
const accuracy = document.getElementById("accuracy");
const netWpm = document.getElementById("net-wpm");
const resultPanel = document.getElementById("time-attack-result");
const saveStatus = document.getElementById("save-status");

function renderStrip() {
  const fragment = document.createDocumentFragment();
  for (const slot of getVisibleSlots(typingState)) {
    const character = document.createElement("span");
    character.classList.add("typing-character", "is-" + slot.status);
    if (slot.isCursor) {
      character.classList.add("is-cursor");
    }
    character.textContent = slot.character;
    fragment.appendChild(character);
  }
  typingArea.replaceChildren(fragment);
}

function renderLive(nowMs) {
  const remainingMs = getTimeAttackRemainingMs(run, nowMs);
  const elapsedMs = durationMs - remainingMs;
  const counts = countBufferMetrics(typingState.typedBuffer, typingState.target);
  const metrics = calculateMetrics(counts, elapsedMs);
  timeRemaining.textContent = formatRemainingSeconds(remainingMs) + " s";
  rawWpm.textContent = metrics.rawWpm.toFixed(1);
  accuracy.textContent = (metrics.accuracy * 100).toFixed(1) + "%";
  netWpm.textContent = metrics.netWpm.toFixed(1);

  if (run.phase === "countdown") {
    const leftMs = getCountdownRemainingMs(run, nowMs);
    status.textContent = "Starting in " + Math.ceil(leftMs / 1000) + "...";
  } else if (run.phase.startsWith("paused")) {
    status.textContent = "Paused. Press Resume to continue.";
  } else if (run.phase === "running") {
    status.textContent = "Running";
  } else {
    status.textContent = "Time up";
  }
  pauseButton.disabled = run.phase.startsWith("paused") || run.phase === "finished";
  resumeButton.disabled = !run.phase.startsWith("paused");
}

function renderResult(result) {
  document.getElementById("result-raw-wpm").textContent = result.rawWpm.toFixed(1);
  document.getElementById("result-accuracy").textContent =
    (result.accuracy * 100).toFixed(1) + "%";
  document.getElementById("result-net-wpm").textContent = result.netWpm.toFixed(1);
  document.getElementById("result-words").textContent = result.wordsTyped;
  document.getElementById("result-time").textContent =
    (result.activeElapsedMs / 1000).toFixed(1) + " s";
  document.getElementById("result-duration").textContent = durationSeconds + " s";
  resultPanel.hidden = false;
}

async function submitResult() {
  const profileId = typingArea.dataset.profileId;
  if (profileId === "") {
    saveStatus.textContent = "Not saved: choose a profile before playing.";
    return;
  }

  const payload = {
    profile_id: Number(profileId),
    duration_seconds: durationSeconds,
    chunk_ids: stream.chunkIds,
    typed_buffer: typingState.typedBuffer,
  };
  try {
    const response = await fetch(typingArea.dataset.saveUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const saved = await response.json();
    saveStatus.textContent = response.ok
      ? "Saved for the active profile."
      : "Not saved: " + saved.error;
  } catch {
    saveStatus.textContent = "Could not confirm the save. Check Progress before trying again.";
  }
}

function finishRun() {
  const counts = countBufferMetrics(typingState.typedBuffer, typingState.target);
  const metrics = calculateMetrics(counts, durationMs);
  const result = {
    ...metrics,
    wordsTyped: countCompletedTargetWords(
      typingState.target, typingState.typedBuffer.length
    ),
    activeElapsedMs: durationMs,
  };
  renderResult(result);
  submitResult();
}

function scheduleNextTransition(nowMs) {
  clearTimeout(transitionTimeoutId);
  if (run.phase !== "countdown" && run.phase !== "running") {
    transitionTimeoutId = null;
    return;
  }

  const remainingMs = run.phase === "countdown"
    ? getCountdownRemainingMs(run, nowMs)
    : getTimeAttackRemainingMs(run, nowMs);
  transitionTimeoutId = setTimeout(() => {
    transitionTimeoutId = null;
    update(performance.now());
    if (transitionTimeoutId === null &&
        (run.phase === "countdown" || run.phase === "running")) {
      scheduleNextTransition(performance.now());
    }
  }, Math.max(1, Math.ceil(remainingMs)));
}

function update(nowMs) {
  const transition = advanceTimeAttackTimer(run, nowMs);
  if (transition.started && run.phase === "running") {
    typingArea.focus();
    scheduleNextTransition(nowMs);
  }
  if (transition.finished) {
    clearTimeout(transitionTimeoutId);
    transitionTimeoutId = null;
    finishRun();
  }
  renderLive(nowMs);
}

function pauseRun(nowMs) {
  const transition = pauseTimeAttackTimer(run, nowMs);
  clearTimeout(transitionTimeoutId);
  transitionTimeoutId = null;
  if (transition.finished) {
    finishRun();
  }
  renderLive(nowMs);
}

function resumeRun(nowMs) {
  if (resumeTimeAttackTimer(run, nowMs)) {
    scheduleNextTransition(nowMs);
    if (run.phase === "running") {
      typingArea.focus();
    }
  }
  renderLive(nowMs);
}

typingArea.addEventListener("keydown", (event) => {
  const nowMs = performance.now();
  update(nowMs);
  const isEditingKey = event.key.length === 1 ||
    ["Backspace", "ArrowLeft", "ArrowRight", "Enter"].includes(event.key);
  if (run.phase !== "running") {
    if (isEditingKey) {
      event.preventDefault();
    }
    return;
  }

  let changed = false;
  if (event.key === "Backspace") {
    event.preventDefault();
    changed = backspaceTimeAttack(typingState);
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    changed = moveTimeAttackCursorLeft(typingState);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    changed = moveTimeAttackCursorRight(typingState);
  } else if (event.key === "Enter") {
    event.preventDefault();
  } else if (event.key.toLowerCase() === "v" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
  } else if (
    event.key.length === 1 &&
    !event.repeat &&
    !event.ctrlKey &&
    !event.altKey &&
    !event.metaKey
  ) {
    event.preventDefault();
    if (typingState.cursorPosition === typingState.typedBuffer.length) {
      ensureStreamLength(
        stream, typingState.typedBuffer.length + WINDOW_CHARACTERS + 1
      );
      typingState.target = stream.target;
    }
    changed = typeTimeAttackCharacter(typingState, event.key);
  }

  if (changed) {
    renderStrip();
    renderLive(nowMs);
  }
});

typingArea.addEventListener("paste", (event) => event.preventDefault());
pauseButton.addEventListener("click", () => pauseRun(performance.now()));
resumeButton.addEventListener("click", () => resumeRun(performance.now()));
window.addEventListener("blur", () => pauseRun(performance.now()));
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    pauseRun(performance.now());
  }
});

renderStrip();
if (document.hidden) {
  pauseRun(performance.now());
} else {
  renderLive(performance.now());
  scheduleNextTransition(performance.now());
}
setInterval(() => update(performance.now()), 50);
