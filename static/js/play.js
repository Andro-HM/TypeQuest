import {
  backspace,
  createTypingState,
  getCharacterStatus,
  moveCursorLeft,
  moveCursorRight,
  typeCharacter,
} from "./typing.js";
import {
  createClock,
  getActiveElapsedMs,
  pauseClock,
  resumeClock,
  startClock,
} from "./clock.js";
import { calculateMetrics, countBufferMetrics } from "./metrics.js";
import { completeClassicRun, createClassicRun } from "./classic.js";

const typingArea = document.getElementById("typing-area");
const state = createTypingState(typingArea.dataset.target);
const clock = createClock();
const classicRun = createClassicRun();
const pauseButton = document.getElementById("pause-button");
const resumeButton = document.getElementById("resume-button");
const timerStatus = document.getElementById("timer-status");
const activeTime = document.getElementById("active-time");
const rawWpm = document.getElementById("raw-wpm");
const accuracy = document.getElementById("accuracy");
const netWpm = document.getElementById("net-wpm");
const resultPanel = document.getElementById("classic-result");
const resultRawWpm = document.getElementById("result-raw-wpm");
const resultAccuracy = document.getElementById("result-accuracy");
const resultNetWpm = document.getElementById("result-net-wpm");
const resultTime = document.getElementById("result-time");
const resultStars = document.getElementById("result-stars");
const saveStatus = document.getElementById("save-status");
const resultNext = document.getElementById("result-next");

function renderTarget() {
  const characters = document.createDocumentFragment();

  for (let index = 0; index < state.target.length; index += 1) {
    const character = document.createElement("span");
    character.classList.add("typing-character");
    character.classList.add("is-" + getCharacterStatus(state, index));

    if (index === state.cursorPosition) {
      character.classList.add("is-cursor");
    }

    character.textContent = state.target[index];
    characters.appendChild(character);
  }

  if (state.cursorPosition === state.target.length) {
    const endCursor = document.createElement("span");
    endCursor.classList.add("typing-cursor-end");
    endCursor.setAttribute("aria-hidden", "true");
    characters.appendChild(endCursor);
  }

  typingArea.replaceChildren(characters);
}

function renderStats() {
  const elapsedMs = getActiveElapsedMs(clock, performance.now());
  const counts = countBufferMetrics(state.typedBuffer, state.target);
  const metrics = calculateMetrics(counts, elapsedMs);

  activeTime.textContent = (elapsedMs / 1000).toFixed(1) + " s";
  rawWpm.textContent = metrics.rawWpm.toFixed(1);
  accuracy.textContent = (metrics.accuracy * 100).toFixed(1) + "%";
  netWpm.textContent = metrics.netWpm.toFixed(1);

  if (classicRun.isComplete) {
    timerStatus.textContent = "Completed";
  } else if (clock.isPaused) {
    timerStatus.textContent = "Paused";
  } else if (clock.hasStarted) {
    timerStatus.textContent = "Running";
  } else {
    timerStatus.textContent = "Ready";
  }
  pauseButton.disabled = classicRun.isComplete || clock.isPaused;
  resumeButton.disabled = classicRun.isComplete || !clock.isPaused;
}

function renderResult(result) {
  resultRawWpm.textContent = result.rawWpm.toFixed(1);
  resultAccuracy.textContent = (result.accuracy * 100).toFixed(1) + "%";
  resultNetWpm.textContent = result.netWpm.toFixed(1);
  resultTime.textContent = (result.completionTimeMs / 1000).toFixed(1) + " s";
  resultStars.textContent = result.starsEarned + " of 3";
  resultPanel.hidden = false;
}

async function submitResult(result) {
  const profileId = typingArea.dataset.profileId;
  const payload = {
    profile_id: profileId === "" ? null : Number(profileId),
    level_id: Number(typingArea.dataset.levelId),
    typed_buffer: state.typedBuffer,
    active_elapsed_ms: result.completionTimeMs,
  };

  try {
    const response = await fetch(typingArea.dataset.saveUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const savedResult = await response.json();
    if (response.ok) {
      saveStatus.textContent = "Saved for the active profile.";
    } else {
      saveStatus.textContent = "Not saved: " + savedResult.error;
    }
  } catch {
    saveStatus.textContent = "Could not confirm the save. Check Progress before trying again.";
  } finally {
    resultNext.hidden = false;
  }
}

typingArea.addEventListener("keydown", (event) => {
  if (classicRun.isComplete || clock.isPaused) {
    const isEditingKey = event.key.length === 1 ||
      ["Backspace", "ArrowLeft", "ArrowRight", "Enter"].includes(event.key);
    if (isEditingKey) {
      event.preventDefault();
    }
    return;
  }

  let changed = false;

  if (event.key === "Backspace") {
    event.preventDefault();
    changed = backspace(state);
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    changed = moveCursorLeft(state);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    changed = moveCursorRight(state);
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
    changed = typeCharacter(state, event.key);
    if (changed && !clock.hasStarted) {
      startClock(clock, performance.now());
    }
  }

  if (changed) {
    let result = null;
    if (state.typedBuffer.length === state.target.length) {
      result = completeClassicRun(classicRun, state, clock, performance.now());
    }

    renderTarget();
    renderStats();
    if (result !== null) {
      renderResult(result);
      submitResult(result);
    }
  }
});

typingArea.addEventListener("paste", (event) => {
  event.preventDefault();
});

pauseButton.addEventListener("click", () => {
  if (classicRun.isComplete) {
    return;
  }
  pauseClock(clock, performance.now());
  renderStats();
});

resumeButton.addEventListener("click", () => {
  if (classicRun.isComplete) {
    return;
  }
  resumeClock(clock, performance.now());
  renderStats();
  typingArea.focus();
});

function pauseForFocusLoss() {
  pauseClock(clock, performance.now());
  renderStats();
}

window.addEventListener("blur", pauseForFocusLoss);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    pauseForFocusLoss();
  }
});

renderTarget();
renderStats();
setInterval(renderStats, 100);
