import {
  backspace,
  createTypingState,
  getCharacterStatus,
  moveCursorLeft,
  moveCursorRight,
  typeCharacter,
} from "./typing.js";

const typingArea = document.getElementById("typing-area");
const state = createTypingState(typingArea.dataset.target);

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

typingArea.addEventListener("keydown", (event) => {
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
  }

  if (changed) {
    renderTarget();
  }
});

typingArea.addEventListener("paste", (event) => {
  event.preventDefault();
});

renderTarget();
