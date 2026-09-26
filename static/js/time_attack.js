import {
  backspace,
  createTypingState,
  getCharacterStatus,
  moveCursorLeft,
  moveCursorRight,
  typeCharacter,
} from "./typing.js";

export const HISTORY_CHARACTERS = 18;
export const WINDOW_CHARACTERS = 60;

export function createTimeAttackState(target) {
  return createTypingState(target);
}

export function getWindowStart(state) {
  // Negative starts leave blank columns so each append visibly shifts the strip.
  return state.typedBuffer.length - HISTORY_CHARACTERS;
}

export function typeTimeAttackCharacter(state, character) {
  return typeCharacter(state, character);
}

export function backspaceTimeAttack(state) {
  return backspace(state);
}

export function moveTimeAttackCursorLeft(state) {
  if (state.cursorPosition <= Math.max(0, getWindowStart(state))) {
    return false;
  }
  return moveCursorLeft(state);
}

export function moveTimeAttackCursorRight(state) {
  return moveCursorRight(state);
}

export function getVisibleSlots(state) {
  const slots = [];
  const start = getWindowStart(state);
  for (let column = 0; column < WINDOW_CHARACTERS; column += 1) {
    const index = start + column;
    slots.push({
      character: index >= 0 && index < state.target.length ? state.target[index] : " ",
      status: index >= 0 && index < state.target.length
        ? getCharacterStatus(state, index) : "untouched",
      isCursor: index === state.cursorPosition,
    });
  }
  return slots;
}
