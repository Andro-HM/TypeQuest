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

let currentLevelIndex = 0;
let targetPassage = "";
let startTime = null;
let timerInterval = null;
let elapsedMilliseconds = 0;
let rawWPM = 0;
let accuracy = 0;
let netWPM = 0;
let isComplete = false;

// Show one page section and move keyboard focus to its heading.
function showScreen(screenId) {
  for (let index = 0; index < screens.length; index += 1) {
    screens[index].hidden = true;
  }
  const screen = document.getElementById(screenId);
  screen.hidden = false;
  screen.querySelector("h1").focus();
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
  targetPassage = levels[currentLevelIndex].passage;
  typingInput.value = "";
  typingInput.maxLength = targetPassage.length;
  typingInput.disabled = false;
  document.getElementById("level-label").textContent = "Classic / Level " + (currentLevelIndex + 1);
  document.getElementById("level-title").textContent = levels[currentLevelIndex].title;
  updateHighlighting();
  updateMetrics();
  showScreen("typing-screen");
  typingInput.focus();
}

// Handle native textarea edits, start timing, and check for completion.
function handleTyping() {
  if (isComplete) {
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
  if (startTime !== null && !isComplete) {
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

// Stop the attempt once and show its final metrics, even if it has mistakes.
function finishLevel() {
  if (isComplete) {
    return;
  }
  clearInterval(timerInterval);
  timerInterval = null;
  updateMetrics();
  isComplete = true;
  typingInput.disabled = true;
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

document.getElementById("start-button").addEventListener("click", showLevelSelection);
document.getElementById("choose-level-button").addEventListener("click", showLevelSelection);
document.getElementById("retry-button").addEventListener("click", startLevel);
for (let index = 0; index < levelButtons.length; index += 1) {
  levelButtons[index].addEventListener("click", startLevel);
}
typingInput.addEventListener("input", handleTyping);
typingInput.addEventListener("keydown", restrictTyping);
typingInput.addEventListener("beforeinput", restrictTyping);
typingInput.addEventListener("paste", restrictTyping);
typingInput.addEventListener("drop", restrictTyping);
