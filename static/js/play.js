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

const typingArea = document.getElementById("typing-area");
const state = createTypingState(typingArea.dataset.target);
const clock = createClock();
const pauseButton = document.getElementById("pause-button");
const resumeButton = document.getElementById("resume-button");
const timerStatus = document.getElementById("timer-status");
const activeTime = document.getElementById("active-time");
const rawWpm = document.getElementById("raw-wpm");
const accuracy = document.getElementById("accuracy");
const netWpm = document.getElementById("net-wpm");

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

  if (clock.isPaused) {
    timerStatus.textContent = "Paused";
  } else if (clock.hasStarted) {
    timerStatus.textContent = "Running";
  } else {
    timerStatus.textContent = "Ready";
  }
  pauseButton.disabled = clock.isPaused;
  resumeButton.disabled = !clock.isPaused;
}

typingArea.addEventListener("keydown", (event) => {
  if (clock.isPaused) {
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
    renderTarget();
    renderStats();
  }
});

typingArea.addEventListener("paste", (event) => {
  event.preventDefault();
});

pauseButton.addEventListener("click", () => {
  pauseClock(clock, performance.now());
  renderStats();
});

resumeButton.addEventListener("click", () => {
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
