export function createTypingState(target) {
  return {
    target: target,
    typedBuffer: "",
    cursorPosition: 0,
  };
}

export function typeCharacter(state, character) {
  if (typeof character !== "string" || character.length !== 1) {
    return false;
  }

  if (state.cursorPosition === state.typedBuffer.length) {
    if (state.typedBuffer.length === state.target.length) {
      return false;
    }
    state.typedBuffer += character;
  } else {
    state.typedBuffer =
      state.typedBuffer.slice(0, state.cursorPosition) +
      character +
      state.typedBuffer.slice(state.cursorPosition + 1);
  }

  state.cursorPosition += 1;
  return true;
}

export function backspace(state) {
  if (state.cursorPosition === 0) {
    return false;
  }

  state.typedBuffer =
    state.typedBuffer.slice(0, state.cursorPosition - 1) +
    state.typedBuffer.slice(state.cursorPosition);
  state.cursorPosition -= 1;
  return true;
}

export function moveCursorLeft(state) {
  if (state.cursorPosition === 0) {
    return false;
  }

  state.cursorPosition -= 1;
  return true;
}

export function moveCursorRight(state) {
  if (state.cursorPosition === state.typedBuffer.length) {
    return false;
  }

  state.cursorPosition += 1;
  return true;
}

export function getCharacterStatus(state, index) {
  if (index >= state.typedBuffer.length) {
    return "untouched";
  }

  if (state.typedBuffer[index] === state.target[index]) {
    return "correct";
  }

  return "incorrect";
}
