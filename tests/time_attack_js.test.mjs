import assert from "node:assert/strict";
import test from "node:test";

import { createChunkStream, ensureStreamLength } from "../static/js/chunk_stream.js";
import {
  createClock, getActiveElapsedMs, pauseClock, resumeClock, startClock,
} from "../static/js/clock.js";
import {
  calculateMetrics, countBufferMetrics, countCompletedTargetWords,
} from "../static/js/metrics.js";
import {
  backspaceTimeAttack, createTimeAttackState, getVisibleSlots,
  getWindowStart, moveTimeAttackCursorLeft, moveTimeAttackCursorRight,
  typeTimeAttackCharacter,
} from "../static/js/time_attack.js";

test("stream uses each chunk once per cycle and avoids a boundary repeat", () => {
  const chunks = Array.from({ length: 100 }, (_, index) => ({
    id: index + 1,
    text: `Chunk ${index + 1}.`,
  }));
  const stream = createChunkStream(chunks, () => 0);
  ensureStreamLength(stream, stream.target.length + 1);
  assert.equal(stream.chunkIds.length, 200);
  assert.equal(new Set(stream.chunkIds.slice(0, 100)).size, 100);
  assert.equal(new Set(stream.chunkIds.slice(100)).size, 100);
  assert.notEqual(stream.chunkIds[99], stream.chunkIds[100]);
  assert.equal(stream.target.includes("  "), false);
  assert.equal(
    stream.target,
    stream.chunkIds.map((id) => chunks[id - 1].text).join(" "),
  );
});

test("append shifts the strip; overwrite does not; Backspace rolls it right", () => {
  const state = createTimeAttackState("x".repeat(200));
  for (let index = 0; index < 25; index += 1) {
    assert.equal(typeTimeAttackCharacter(state, "x"), true);
  }
  assert.equal(getWindowStart(state), 7);
  assert.equal(getVisibleSlots(state).length, 60);
  for (let index = 0; index < 30; index += 1) {
    moveTimeAttackCursorLeft(state);
  }
  assert.equal(state.cursorPosition, 7);
  assert.equal(moveTimeAttackCursorLeft(state), false);
  assert.equal(typeTimeAttackCharacter(state, "y"), true);
  assert.equal(state.typedBuffer.length, 25);
  assert.equal(getWindowStart(state), 7);
  assert.equal(backspaceTimeAttack(state), true);
  assert.equal(state.typedBuffer.length, 24);
  assert.equal(getWindowStart(state), 6);
  assert.equal(moveTimeAttackCursorRight(state), true);
  for (let index = 0; index < 40; index += 1) {
    moveTimeAttackCursorRight(state);
  }
  assert.equal(state.cursorPosition, state.typedBuffer.length);
  assert.equal(moveTimeAttackCursorRight(state), false);
});

test("metrics count retained positions and only words with reached boundaries", () => {
  const target = "one two three four";
  assert.equal(countCompletedTargetWords(target, 7), 1);
  assert.equal(countCompletedTargetWords(target, 8), 2);
  const counts = countBufferMetrics("one tXo ", target);
  const result = calculateMetrics(counts, 30000);
  assert.equal(counts.retainedEnteredCharacters, 8);
  assert.equal(counts.correctPositions, 7);
  assert.equal(result.rawWpm, 3.2);
  assert.equal(result.accuracy, 7 / 8);
  assert.equal(result.netWpm, 3.2 * 7 / 8);
});

test("active clock excludes paused time", () => {
  const clock = createClock();
  assert.equal(getActiveElapsedMs(clock, 3000), 0);
  startClock(clock, 3000);
  pauseClock(clock, 4000);
  assert.equal(getActiveElapsedMs(clock, 10000), 1000);
  resumeClock(clock, 10000);
  assert.equal(getActiveElapsedMs(clock, 11000), 2000);
});
