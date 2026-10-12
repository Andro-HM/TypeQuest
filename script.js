const levels = [
  {
    title: "A quiet morning",
    passage: "The morning sun lit the kitchen. I opened a window, poured a glass of water, and made a small plan for the day. One calm step was enough to begin."
  },
  {
    title: "A shared idea",
    passage: "Our team met after class to sketch a new idea. We asked, 'What would make this easier?' Each person added a detail, and the simple drawing became a useful plan."
  },
  {
    title: "Keep exploring",
    passage: "A narrow path led past the library and into a quiet garden. We noticed fresh leaves, a bright blue bench, and a bird beside the fountain. Small discoveries made the familiar walk feel new."
  }
];

const typingInput = document.getElementById("typing-input");
const targetDisplay = document.getElementById("target-passage");
const screens = document.querySelectorAll(".screen");
const levelButtons = document.querySelectorAll(".level-button");
const pauseButton = document.getElementById("pause-button");
const playButton = document.getElementById("play-button");
const typingStatus = document.getElementById("typing-status");
const homeNav = document.getElementById("home-nav");
const playNav = document.getElementById("play-nav");

let currentLevelIndex = 0;
let targetPassage = "";
let startTime = null;
let timerInterval = null;
let elapsedMilliseconds = 0;
let rawWPM = 0;
let accuracy = 0;
let netWPM = 0;
let isComplete = false;
let isPaused = false;

// Show one section, mark its navigation tab, and focus its heading.
function showScreen(screenId) {
  for (let index = 0; index < screens.length; index += 1) {
    screens[index].hidden = true;
  }
  const screen = document.getElementById(screenId);
  screen.hidden = false;
  homeNav.classList.remove("is-active");
  playNav.classList.remove("is-active");
  homeNav.removeAttribute("aria-current");
  playNav.removeAttribute("aria-current");
  if (screenId === "home-screen") {
    homeNav.classList.add("is-active");
    homeNav.setAttribute("aria-current", "page");
  } else {
    playNav.classList.add("is-active");
    playNav.setAttribute("aria-current", "page");
  }
  screen.querySelector("h1").focus();
}

// Open Home and pause any unfinished typing attempt.
function showHome() {
  pauseLevel();
  showScreen("home-screen");
}

// Open the game-mode choices and pause any unfinished typing attempt.
function showPlay() {
  pauseLevel();
  showScreen("play-screen");
}

// Open the three freely selectable Classic levels.
function showLevelSelection() {
  showScreen("levels-screen");
}

// Load a chosen level, or retry the current one, with a fresh attempt.
function startLevel(event) {
  if (event.currentTarget.hasAttribute("data-level")) {
    currentLevelIndex = Number(event.currentTarget.dataset.level);
  }
  clearInterval(timerInterval);
  timerInterval = null;
  startTime = null;
  elapsedMilliseconds = 0;
  rawWPM = 0;
  accuracy = 0;
  netWPM = 0;
  isComplete = false;
  isPaused = false;
  targetPassage = levels[currentLevelIndex].passage;
  typingInput.value = "";
  typingInput.maxLength = targetPassage.length;
  typingInput.disabled = false;
  pauseButton.disabled = true;
  playButton.disabled = true;
  typingStatus.textContent = "Start typing to begin.";
  document.getElementById("level-label").textContent = "Classic / Level " + (currentLevelIndex + 1);
  document.getElementById("level-title").textContent = levels[currentLevelIndex].title;
  updateHighlighting();
  updateMetrics();
  showScreen("typing-screen");
  typingInput.focus();
}

// Handle native textarea edits, start timing, and check for completion.
function handleTyping() {
  if (isComplete || isPaused) {
    return;
  }
  const enteredText = typingInput.value;
  let cleanText = "";
  for (let index = 0; index < enteredText.length; index += 1) {
    if (enteredText[index] !== "\n" && enteredText[index] !== "\r" && cleanText.length < targetPassage.length) {
      cleanText += enteredText[index];
    }
  }
  if (enteredText !== cleanText) {
    typingInput.value = cleanText;
  }
  if (startTime === null && typingInput.value.length > 0) {
    startTime = performance.now();
    timerInterval = setInterval(updateMetrics, 100);
    pauseButton.disabled = false;
    typingStatus.textContent = "Typing";
  }
  updateHighlighting();
  updateMetrics();
  if (typingInput.value.length === targetPassage.length) {
    finishLevel();
  }
}

// Count exact matches at the same positions, including spaces and case.
function countCorrectCharacters() {
  let correctPositions = 0;
  const typedText = typingInput.value;
  for (let index = 0; index < typedText.length; index += 1) {
    if (typedText[index] === targetPassage[index]) {
      correctPositions += 1;
    }
  }
  return correctPositions;
}

// Calculate unrounded metrics from retained text and display one decimal place.
function updateMetrics() {
  if (startTime !== null && !isComplete && !isPaused) {
    elapsedMilliseconds = performance.now() - startTime;
  }
  const typedLength = typingInput.value.length;
  const elapsedMinutes = elapsedMilliseconds / 60000;
  const correctPositions = countCorrectCharacters();
  rawWPM = 0;
  accuracy = 0;
  if (elapsedMinutes > 0) {
    rawWPM = (typedLength / 5) / elapsedMinutes;
  }
  if (typedLength > 0) {
    accuracy = correctPositions / typedLength;
  }
  netWPM = rawWPM * accuracy;
  document.getElementById("elapsed-time").textContent = (elapsedMilliseconds / 1000).toFixed(1) + " s";
  document.getElementById("raw-wpm").textContent = rawWPM.toFixed(1);
  document.getElementById("accuracy").textContent = (accuracy * 100).toFixed(1) + "%";
  document.getElementById("net-wpm").textContent = netWPM.toFixed(1);
  document.getElementById("character-count").textContent = typedLength + " / " + targetPassage.length + " characters entered";
}

// Render each target character with its correct, incorrect, or untouched state.
function updateHighlighting() {
  const typedText = typingInput.value;
  targetDisplay.replaceChildren();
  for (let index = 0; index < targetPassage.length; index += 1) {
    const character = document.createElement("span");
    character.textContent = targetPassage[index];
    if (index >= typedText.length) {
      character.className = "untouched";
    } else if (typedText[index] === targetPassage[index]) {
      character.className = "correct";
    } else {
      character.className = "incorrect";
    }
    targetDisplay.appendChild(character);
  }
}

// Freeze active time and prevent editing until Play is pressed.
function pauseLevel() {
  if (startTime === null || isPaused || isComplete) {
    return;
  }
  updateMetrics();
  isPaused = true;
  clearInterval(timerInterval);
  timerInterval = null;
  typingInput.disabled = true;
  pauseButton.disabled = true;
  playButton.disabled = false;
  typingStatus.textContent = "Paused. Press Play to continue.";
}

// Resume from the saved elapsed time by adjusting the start timestamp.
function playLevel() {
  if (!isPaused || isComplete) {
    return;
  }
  startTime = performance.now() - elapsedMilliseconds;
  isPaused = false;
  typingInput.disabled = false;
  pauseButton.disabled = false;
  playButton.disabled = true;
  typingStatus.textContent = "Typing";
  timerInterval = setInterval(updateMetrics, 100);
  updateMetrics();
  typingInput.focus();
}

// Stop the attempt once and show its final metrics, even if it has mistakes.
function finishLevel() {
  if (isComplete || isPaused) {
    return;
  }
  clearInterval(timerInterval);
  timerInterval = null;
  updateMetrics();
  isComplete = true;
  typingInput.disabled = true;
  pauseButton.disabled = true;
  playButton.disabled = true;
  typingStatus.textContent = "Complete";
  document.getElementById("result-level").textContent = "Level " + (currentLevelIndex + 1) + ": " + levels[currentLevelIndex].title;
  document.getElementById("result-time").textContent = (elapsedMilliseconds / 1000).toFixed(1) + " s";
  document.getElementById("result-raw-wpm").textContent = rawWPM.toFixed(1);
  document.getElementById("result-accuracy").textContent = (accuracy * 100).toFixed(1) + "%";
  document.getElementById("result-net-wpm").textContent = netWPM.toFixed(1);
  showScreen("results-screen");
}

// Block paste, dropped text, and line breaks before they change the textarea.
function restrictTyping(event) {
  if (event.type === "paste" || event.type === "drop" || event.key === "Enter" ||
      event.inputType === "insertFromPaste" || event.inputType === "insertFromDrop" ||
      event.inputType === "insertLineBreak" || event.inputType === "insertParagraph") {
    event.preventDefault();
  }
}

homeNav.addEventListener("click", showHome);
playNav.addEventListener("click", showPlay);
document.getElementById("start-button").addEventListener("click", showPlay);
document.getElementById("classic-button").addEventListener("click", showLevelSelection);
document.getElementById("choose-level-button").addEventListener("click", showLevelSelection);
document.getElementById("retry-button").addEventListener("click", startLevel);
pauseButton.addEventListener("click", pauseLevel);
playButton.addEventListener("click", playLevel);
for (let index = 0; index < levelButtons.length; index += 1) {
  levelButtons[index].addEventListener("click", startLevel);
}
typingInput.addEventListener("input", handleTyping);
typingInput.addEventListener("keydown", restrictTyping);
typingInput.addEventListener("beforeinput", restrictTyping);
typingInput.addEventListener("paste", restrictTyping);
typingInput.addEventListener("drop", restrictTyping);
