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
import {
  advanceTimeAttackTimer, createTimeAttackTimer, formatRemainingSeconds,
  getCountdownRemainingMs, getTimeAttackRemainingMs, pauseTimeAttackTimer,
  resumeTimeAttackTimer,
} from "../static/js/time_attack_timer.js";

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

test("countdown gives every duration its full active time", () => {
  for (const durationSeconds of [30, 60, 120, 180, 300]) {
    const durationMs = durationSeconds * 1000;
    const timer = createTimeAttackTimer(durationMs, 100);
    assert.equal(getTimeAttackRemainingMs(timer, 3099), durationMs);
    assert.equal(advanceTimeAttackTimer(timer, 3099).started, false);

    const start = advanceTimeAttackTimer(timer, 3100);
    assert.deepEqual(start, { started: true, finished: false });
    assert.equal(getActiveElapsedMs(timer.clock, 3100), 0);
    assert.equal(getTimeAttackRemainingMs(timer, 3100), durationMs);
    assert.equal(advanceTimeAttackTimer(timer, 3100 + durationMs - 1).finished, false);
    assert.equal(advanceTimeAttackTimer(timer, 3100 + durationMs).finished, true);
    assert.equal(getActiveElapsedMs(timer.clock, 3100 + durationMs), durationMs);
    assert.equal(getTimeAttackRemainingMs(timer, 3100 + durationMs), 0);
    assert.equal(advanceTimeAttackTimer(timer, 3100 + durationMs + 1000).finished, false);
  }
});

test("pause, resume, and repeated pauses preserve active time", () => {
  const timer = createTimeAttackTimer(30000, 0);
  advanceTimeAttackTimer(timer, 3000);
  pauseTimeAttackTimer(timer, 13000);
  assert.equal(timer.phase, "paused-running");
  assert.equal(getTimeAttackRemainingMs(timer, 100000), 20000);
  pauseTimeAttackTimer(timer, 100000);
  assert.equal(getTimeAttackRemainingMs(timer, 100000), 20000);

  assert.equal(resumeTimeAttackTimer(timer, 100000), true);
  assert.equal(resumeTimeAttackTimer(timer, 100001), false);
  assert.equal(getTimeAttackRemainingMs(timer, 105000), 15000);
  pauseTimeAttackTimer(timer, 105000);
  assert.equal(getTimeAttackRemainingMs(timer, 200000), 15000);
  resumeTimeAttackTimer(timer, 200000);
  assert.equal(advanceTimeAttackTimer(timer, 214999).finished, false);
  assert.equal(advanceTimeAttackTimer(timer, 215000).finished, true);
  assert.equal(getActiveElapsedMs(timer.clock, 215000), 30000);
});

test("paused countdown resumes where it stopped", () => {
  const timer = createTimeAttackTimer(30000, 0);
  pauseTimeAttackTimer(timer, 1000);
  assert.equal(timer.phase, "paused-countdown");
  assert.equal(getCountdownRemainingMs(timer, 100000), 2000);
  assert.equal(getTimeAttackRemainingMs(timer, 100000), 30000);
  pauseTimeAttackTimer(timer, 100000);
  resumeTimeAttackTimer(timer, 100000);
  assert.equal(advanceTimeAttackTimer(timer, 101999).started, false);
  assert.equal(advanceTimeAttackTimer(timer, 102000).started, true);
  assert.equal(getTimeAttackRemainingMs(timer, 102000), 30000);
});

test("late callbacks finalize once at the exact deadline", () => {
  const timer = createTimeAttackTimer(30000, 0);
  const transition = advanceTimeAttackTimer(timer, 34000);
  assert.deepEqual(transition, { started: true, finished: true });
  assert.equal(timer.phase, "finished");
  assert.equal(getActiveElapsedMs(timer.clock, 34000), 30000);
  assert.equal(getTimeAttackRemainingMs(timer, 34000), 0);
  assert.deepEqual(advanceTimeAttackTimer(timer, 50000), {
    started: false, finished: false,
  });
  assert.equal(formatRemainingSeconds(40), "0.1");
  assert.equal(formatRemainingSeconds(0), "0.0");
  assert.equal(formatRemainingSeconds(-10), "0.0");
});
