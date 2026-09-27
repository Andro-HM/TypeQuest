import assert from "node:assert/strict";
import test from "node:test";

import {
  backspace, createTypingState, getCharacterStatus,
  moveCursorLeft, moveCursorRight, typeCharacter,
} from "../static/js/typing.js";
import {
  createClock, getActiveElapsedMs, pauseClock, resumeClock, startClock,
} from "../static/js/clock.js";
import { calculateMetrics, countBufferMetrics } from "../static/js/metrics.js";
import {
  completeClassicRun, createClassicRun, starsForAccuracy,
} from "../static/js/classic.js";

test("typing appends, compares exactly, and cannot pass the target length", () => {
  const state = createTypingState("Ab!");
  assert.equal(typeCharacter(state, "a"), true);
  assert.equal(getCharacterStatus(state, 0), "incorrect");
  assert.equal(typeCharacter(state, "B"), true);
  assert.equal(getCharacterStatus(state, 1), "incorrect");
  assert.equal(typeCharacter(state, "!"), true);
  assert.equal(getCharacterStatus(state, 2), "correct");
  assert.equal(state.typedBuffer.length, 3);
  assert.equal(typeCharacter(state, "x"), false);
  assert.equal(state.typedBuffer, "aB!");
});

test("arrows stay in the buffer; overwrite keeps length; Backspace shrinks it", () => {
  const state = createTypingState("Ab!");
  assert.equal(moveCursorLeft(state), false);
  assert.equal(moveCursorRight(state), false);
  typeCharacter(state, "a");
  typeCharacter(state, "b");
  assert.equal(moveCursorLeft(state), true);
  assert.equal(moveCursorLeft(state), true);
  assert.equal(moveCursorLeft(state), false);
  assert.equal(typeCharacter(state, "A"), true);
  assert.equal(state.typedBuffer, "Ab");
  assert.equal(state.typedBuffer.length, 2);
  assert.equal(moveCursorRight(state), true);
  assert.equal(moveCursorRight(state), false);
  assert.equal(backspace(state), true);
  assert.equal(state.typedBuffer, "A");
  assert.equal(state.cursorPosition, 1);
  assert.equal(backspace(state), true);
  assert.equal(backspace(state), false);
});

test("clock excludes pauses and metrics count retained characters", () => {
  const clock = createClock();
  assert.equal(getActiveElapsedMs(clock, 1000), 0);
  startClock(clock, 1000);
  pauseClock(clock, 2000);
  assert.equal(getActiveElapsedMs(clock, 9000), 1000);
  resumeClock(clock, 9000);
  assert.equal(getActiveElapsedMs(clock, 10000), 2000);

  const counts = countBufferMetrics("aXc", "abc");
  const metrics = calculateMetrics(counts, 30000);
  assert.equal(metrics.retainedEnteredCharacters, 3);
  assert.equal(metrics.opportunityPositions, 3);
  assert.equal(metrics.correctPositions, 2);
  assert.equal(metrics.rawWpm, 1.2);
  assert.equal(metrics.accuracy, 2 / 3);
  assert.equal(metrics.netWpm, 1.2 * 2 / 3);
  assert.equal(calculateMetrics(countBufferMetrics("", "abc"), 0).rawWpm, 0);
});

test("star thresholds use unrounded accuracy", () => {
  assert.equal(starsForAccuracy(0.899999), 1);
  assert.equal(starsForAccuracy(0.90), 2);
  assert.equal(starsForAccuracy(0.949999), 2);
  assert.equal(starsForAccuracy(0.95), 3);
});

test("Classic completes only at current buffer length, even with errors", () => {
  const state = createTypingState("abc");
  const clock = createClock();
  const run = createClassicRun();
  startClock(clock, 1000);
  typeCharacter(state, "x");
  typeCharacter(state, "b");
  assert.equal(completeClassicRun(run, state, clock, 2000), null);
  moveCursorLeft(state);
  typeCharacter(state, "b");
  assert.equal(state.typedBuffer.length, 2);
  assert.equal(completeClassicRun(run, state, clock, 2500), null);
  typeCharacter(state, "c");
  const result = completeClassicRun(run, state, clock, 3000);
  assert.equal(result.starsEarned, 1);
  assert.equal(result.accuracy, 2 / 3);
  assert.equal(result.completionTimeMs, 2000);
  assert.equal(completeClassicRun(run, state, clock, 4000), null);
});
