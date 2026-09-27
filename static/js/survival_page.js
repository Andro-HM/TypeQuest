import {
  advanceSurvivalRun, backspaceSurvival, createSurvivalRun,
  damageThreshold, getScrollFraction, getSurvivalMetrics,
  getVisibleSurvivalSlots, moveSurvivalCursorLeft,
  moveSurvivalCursorRight, tierForElapsedMs, typeSurvivalCharacter,
} from "./survival.js";
import {
  advanceSurvivalTimer, createSurvivalTimer, finishSurvivalTimer,
  getSurvivalCountdownMs, getSurvivalElapsedMs, pauseSurvivalTimer,
  resumeSurvivalTimer,
} from "./survival_timer.js";

const chunks = JSON.parse(document.getElementById("survival-chunks").textContent);
const area = document.getElementById("survival-area");
const track = document.getElementById("survival-track");
const run = createSurvivalRun(chunks);
const timer = createSurvivalTimer(performance.now());
const pauseButton = document.getElementById("survival-pause");
const resumeButton = document.getElementById("survival-resume");
const status = document.getElementById("survival-status");
const resultPanel = document.getElementById("survival-result");
const saveStatus = document.getElementById("survival-save-status");
let frameId = null;
let resultShown = false;

function renderStrip(elapsedMs) {
  const characters = document.createDocumentFragment();
  for (const slot of getVisibleSurvivalSlots(run)) {
    const character = document.createElement("span");
    character.classList.add(
      "typing-character", "survival-character", "is-" + slot.status
    );
    if (slot.isCursor) {
      character.classList.add("is-cursor");
    }
    character.textContent = slot.character;
    characters.appendChild(character);
  }
  track.replaceChildren(characters);
  const characterWidth = track.firstElementChild.getBoundingClientRect().width;
  track.style.transform =
    "translateX(-" + getScrollFraction(run, elapsedMs) * characterWidth + "px)";
}

function render(nowMs) {
  const elapsedMs = getSurvivalElapsedMs(timer, nowMs);
  const metrics = getSurvivalMetrics(run, elapsedMs);
  document.getElementById("survival-time").textContent =
    (elapsedMs / 1000).toFixed(1) + " s";
  document.getElementById("survival-net-wpm").textContent = metrics.netWpm.toFixed(1);
  document.getElementById("survival-accuracy").textContent =
    (metrics.accuracy * 100).toFixed(1) + "%";
  document.getElementById("survival-hearts").textContent =
    "♥ " + (run.halfHeartUnits / 2).toFixed(1) + " / 3";
  document.getElementById("survival-tier").textContent =
    tierForElapsedMs(elapsedMs) + " / 5";
  document.getElementById("survival-damage").textContent =
    run.damageCounter + " / " + damageThreshold(run.damageStage) +
    " mistakes toward the next half heart";

  if (timer.phase === "countdown") {
    status.textContent = "Starting in " +
      Math.ceil(getSurvivalCountdownMs(timer, nowMs) / 1000) + "...";
  } else if (timer.phase.startsWith("paused")) {
    status.textContent = "Paused. Press Resume to continue.";
  } else if (timer.phase === "running") {
    status.textContent = "Running";
  } else {
    status.textContent = "Run ended";
  }
  pauseButton.disabled = timer.phase.startsWith("paused") || timer.phase === "finished";
  resumeButton.disabled = !timer.phase.startsWith("paused");
  renderStrip(elapsedMs);
}

function showResult(result) {
  document.getElementById("survival-result-time").textContent =
    (result.activeElapsedMs / 1000).toFixed(1) + " s";
  document.getElementById("survival-result-tier").textContent =
    result.tierReached + " / 5";
  document.getElementById("survival-result-raw").textContent = result.rawWpm.toFixed(1);
  document.getElementById("survival-result-accuracy").textContent =
    (result.accuracy * 100).toFixed(1) + "%";
  document.getElementById("survival-result-net").textContent = result.netWpm.toFixed(1);
  resultPanel.hidden = false;
}

async function saveResult() {
  const profileId = area.dataset.profileId;
  if (profileId === "") {
    saveStatus.textContent = "Not saved: choose a profile before playing.";
    return;
  }
  const payload = {
    profile_id: Number(profileId),
    chunk_ids: run.stream.chunkIds,
    finalized_entries: run.finalizedEntries,
    active_buffer: run.typingState.typedBuffer,
  };
  try {
    const response = await fetch(area.dataset.saveUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const saved = await response.json();
    if (response.ok) {
      showResult({
        activeElapsedMs: saved.active_elapsed_ms,
        tierReached: saved.tier_reached,
        rawWpm: saved.raw_wpm,
        accuracy: saved.accuracy,
        netWpm: saved.net_wpm,
      });
      saveStatus.textContent = "Saved for the active profile.";
    } else {
      saveStatus.textContent = "Not saved: " + saved.error;
    }
  } catch {
    saveStatus.textContent = "Could not confirm the save. Check Progress before trying again.";
  }
}

function finishRun() {
  if (resultShown) {
    return;
  }
  resultShown = true;
  const metrics = getSurvivalMetrics(run, run.deathElapsedMs);
  showResult({
    activeElapsedMs: run.deathElapsedMs,
    tierReached: tierForElapsedMs(run.deathElapsedMs),
    rawWpm: metrics.rawWpm,
    accuracy: metrics.accuracy,
    netWpm: metrics.netWpm,
  });
  saveResult();
}

function update(nowMs) {
  if (advanceSurvivalTimer(timer, nowMs)) {
    area.focus();
  }
  if (timer.phase === "running") {
    advanceSurvivalRun(run, getSurvivalElapsedMs(timer, nowMs));
    if (run.isDead) {
      finishSurvivalTimer(timer, run.deathElapsedMs);
      finishRun();
    }
  }
  render(nowMs);
}

function scheduleFrame() {
  if (frameId === null && (timer.phase === "countdown" || timer.phase === "running")) {
    frameId = requestAnimationFrame((nowMs) => {
      frameId = null;
      update(nowMs);
      scheduleFrame();
    });
  }
}

function pauseRun(nowMs) {
  update(nowMs);
  pauseSurvivalTimer(timer, nowMs);
  if (frameId !== null) {
    cancelAnimationFrame(frameId);
    frameId = null;
  }
  render(nowMs);
}

function resumeRun(nowMs) {
  if (resumeSurvivalTimer(timer, nowMs)) {
    if (timer.phase === "running") {
      area.focus();
    }
    scheduleFrame();
  }
  render(nowMs);
}

area.addEventListener("keydown", (event) => {
  const nowMs = performance.now();
  update(nowMs);
  const isEditingKey = event.key.length === 1 ||
    ["Backspace", "ArrowLeft", "ArrowRight", "Enter"].includes(event.key);
  if (timer.phase !== "running") {
    if (isEditingKey) {
      event.preventDefault();
    }
    return;
  }

  let changed = false;
  if (event.key === "Backspace") {
    event.preventDefault();
    changed = backspaceSurvival(run);
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    changed = moveSurvivalCursorLeft(run);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    changed = moveSurvivalCursorRight(run);
  } else if (event.key === "Enter") {
    event.preventDefault();
  } else if (event.key.toLowerCase() === "v" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
  } else if (
    event.key.length === 1 && !event.repeat &&
    !event.ctrlKey && !event.altKey && !event.metaKey
  ) {
    event.preventDefault();
    changed = typeSurvivalCharacter(run, event.key);
  }
  if (changed) {
    render(nowMs);
  }
});

area.addEventListener("paste", (event) => event.preventDefault());
pauseButton.addEventListener("click", () => pauseRun(performance.now()));
resumeButton.addEventListener("click", () => resumeRun(performance.now()));
window.addEventListener("blur", () => pauseRun(performance.now()));
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    pauseRun(performance.now());
  }
});

render(performance.now());
if (document.hidden) {
  pauseRun(performance.now());
} else {
  scheduleFrame();
}
