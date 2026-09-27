import assert from "node:assert/strict";
import test from "node:test";

import {
  advanceSurvivalRun, backspaceSurvival, createSurvivalRun, damageThreshold,
  getScrollFraction, getSurvivalMetrics, moveSurvivalCursorLeft,
  moveSurvivalCursorRight, scrollDistance, survivalSpeedCps,
  tierForElapsedMs, timeForDistance, typeSurvivalCharacter,
} from "../static/js/survival.js";
import {
  createSurvivalStream, ensureSurvivalLength,
} from "../static/js/survival_stream.js";
import {
  advanceSurvivalTimer, createSurvivalTimer, finishSurvivalTimer,
  getSurvivalCountdownMs, getSurvivalElapsedMs, pauseSurvivalTimer,
  resumeSurvivalTimer,
} from "../static/js/survival_timer.js";

function chunks() {
  return Array.from({ length: 100 }, (_, index) => ({
    id: index + 1,
    tier: Math.floor(index / 20) + 1,
    text: "Chunk " + (index + 1) + " has local text.",
  }));
}

test("speed, analytic distance, inverse, and tier mapping", () => {
  assert.equal(survivalSpeedCps(0), 1.5);
  assert.equal(survivalSpeedCps(60), 2);
  assert.equal(survivalSpeedCps(300), 4);
  assert.equal(survivalSpeedCps(600), 4);
  assert.equal(scrollDistance(0), 0);
  assert.equal(scrollDistance(60), 105);
  assert.equal(scrollDistance(300), 825);
  assert.equal(scrollDistance(310), 865);
  for (const distance of [1, 36, 105, 240, 405, 600, 825, 1000]) {
    assert.ok(Math.abs(scrollDistance(timeForDistance(distance)) - distance) < 1e-8);
  }
  assert.deepEqual(
    [0, 60000, 120000, 180000, 240000, 300000, 600000]
      .map(tierForElapsedMs),
    [1, 2, 3, 4, 5, 5, 5],
  );
});

test("tier stream shuffles without replacement and avoids cycle boundary repeats", () => {
  const stream = createSurvivalStream(chunks(), () => 0);
  ensureSurvivalLength(stream, 1000, 1);
  assert.equal(new Set(stream.chunkIds.slice(0, 20)).size, 20);
  assert.equal(new Set(stream.chunkIds.slice(20, 40)).size, 20);
  assert.notEqual(stream.chunkIds[19], stream.chunkIds[20]);
  assert.ok(stream.chunkIds.slice(0, 40).every((id) => id <= 20));
  const previousLength = stream.target.length;
  ensureSurvivalLength(stream, previousLength + 1, 2);
  assert.ok(stream.chunkIds.at(-1) >= 21 && stream.chunkIds.at(-1) <= 40);
  assert.equal(stream.target.includes("  "), false);
});

test("delayed updates finalize each untyped position once", () => {
  const run = createSurvivalRun(chunks(), () => 0);
  const lateTimeMs = timeForDistance(4) * 1000 + 1;
  assert.equal(advanceSurvivalRun(run, lateTimeMs), true);
  assert.equal(run.finalizedCount, 4);
  assert.deepEqual(run.finalizedEntries, [null, null, null, null]);
  assert.equal(run.damageCounter, 4);
  assert.equal(run.halfHeartUnits, 6);
  assert.equal(advanceSurvivalRun(run, lateTimeMs), false);
  assert.equal(run.finalizedEntries.length, 4);
  assert.ok(getScrollFraction(run, lateTimeMs) > 0);
});

test("typed finalization is immutable and shifts the remaining active buffer", () => {
  const run = createSurvivalRun(chunks(), () => 0);
  const first = run.stream.target[0];
  const second = run.stream.target[1];
  typeSurvivalCharacter(run, first);
  typeSurvivalCharacter(run, second);
  advanceSurvivalRun(run, timeForDistance(1) * 1000 + 1);
  assert.deepEqual(run.finalizedEntries, [first]);
  assert.equal(run.finalizedEnteredCharacters, 1);
  assert.equal(run.finalizedCorrectPositions, 1);
  assert.equal(run.typingState.typedBuffer, second);
  assert.equal(run.typingState.cursorPosition, 1);
  assert.equal(backspaceSurvival(run), true);
  assert.equal(backspaceSurvival(run), false);
  assert.equal(moveSurvivalCursorLeft(run), false);
  assert.equal(run.finalizedEntries[0], first);
});

test("the active buffer has a 60-character cap and overwrite keeps its length", () => {
  const run = createSurvivalRun(chunks(), () => 0);
  for (let index = 0; index < 60; index += 1) {
    assert.equal(typeSurvivalCharacter(run, "x"), true);
  }
  assert.equal(typeSurvivalCharacter(run, "y"), false);
  assert.equal(moveSurvivalCursorLeft(run), true);
  assert.equal(typeSurvivalCharacter(run, "y"), true);
  assert.equal(run.typingState.typedBuffer.length, 60);
  assert.equal(moveSurvivalCursorRight(run), false);
  advanceSurvivalRun(run, timeForDistance(1) * 1000 + 1);
  assert.equal(run.typingState.typedBuffer.length, 59);
  assert.equal(typeSurvivalCharacter(run, "z"), true);
});

test("final metrics include finalized nulls and entered active positions only", () => {
  const run = createSurvivalRun(chunks(), () => 0);
  typeSurvivalCharacter(run, run.stream.target[0]);
  advanceSurvivalRun(run, timeForDistance(1) * 1000 + 1);
  advanceSurvivalRun(run, timeForDistance(2) * 1000 + 1);
  typeSurvivalCharacter(run, run.stream.target[2]);
  typeSurvivalCharacter(run, "@");
  const metrics = getSurvivalMetrics(run, 10000);
  assert.deepEqual(run.finalizedEntries, [run.stream.target[0], null]);
  assert.equal(metrics.retainedEnteredCharacters, 3);
  assert.equal(metrics.opportunityPositions, 4);
  assert.equal(metrics.correctPositions, 2);
  assert.equal(metrics.accuracy, 0.5);
  assert.equal(metrics.rawWpm, 3.6);
  assert.equal(metrics.netWpm, 1.8);
});

test("damage thresholds, stage reset, half hearts, and exact fatal crossing", () => {
  assert.deepEqual(
    [0, 1, 2, 3, 4, 5, 6].map(damageThreshold),
    [6, 5, 4, 3, 2, 1, 1],
  );
  const run = createSurvivalRun(chunks(), () => 0);
  advanceSurvivalRun(run, timeForDistance(5) * 1000 + 1);
  assert.equal(run.damageCounter, 5);
  advanceSurvivalRun(run, timeForDistance(6) * 1000 + 1);
  assert.equal(run.halfHeartUnits, 5);
  assert.equal(run.damageCounter, 0);
  advanceSurvivalRun(run, timeForDistance(35) * 1000 + 1);
  assert.equal(run.halfHeartUnits, 1);
  advanceSurvivalRun(run, 100000);
  assert.equal(run.isDead, true);
  assert.equal(run.halfHeartUnits, 0);
  assert.equal(run.finalizedCount, 36);
  assert.equal(run.finalizedEntries.length, 36);
  assert.ok(Math.abs(run.deathElapsedMs - timeForDistance(36) * 1000) < 1e-7);
  assert.equal(advanceSurvivalRun(run, 200000), false);
  assert.equal(typeSurvivalCharacter(run, "x"), false);
});

test("a new active minute resets pending damage even after a late update", () => {
  const run = createSurvivalRun(chunks(), () => 0);
  run.finalizedCount = 104;
  run.finalizedEntries = Array(104).fill(null);
  run.damageCounter = 4;
  run.damageStage = 0;
  advanceSurvivalRun(run, 60001);
  assert.equal(run.finalizedCount, 105);
  assert.equal(run.damageStage, 1);
  assert.equal(run.damageCounter, 1);
  assert.equal(run.halfHeartUnits, 6);
});

test("damage counter resets at the minute boundary without another crossing", () => {
  const run = createSurvivalRun(chunks(), () => 0);
  run.finalizedCount = 105;
  run.finalizedEntries = Array(105).fill(null);
  run.damageCounter = 4;
  run.damageStage = 0;
  advanceSurvivalRun(run, 60001);
  assert.equal(run.finalizedCount, 105);
  assert.equal(run.damageStage, 1);
  assert.equal(run.damageCounter, 0);
});

test("countdown, pause, and resume exclude inactive time", () => {
  const timer = createSurvivalTimer(0);
  assert.equal(getSurvivalElapsedMs(timer, 2999), 0);
  assert.equal(advanceSurvivalTimer(timer, 2999), false);
  pauseSurvivalTimer(timer, 1000);
  assert.equal(getSurvivalCountdownMs(timer, 90000), 2000);
  assert.equal(resumeSurvivalTimer(timer, 90000), true);
  assert.equal(advanceSurvivalTimer(timer, 91999), false);
  assert.equal(advanceSurvivalTimer(timer, 92000), true);
  assert.equal(getSurvivalElapsedMs(timer, 92000), 0);
  pauseSurvivalTimer(timer, 102000);
  assert.equal(getSurvivalElapsedMs(timer, 200000), 10000);
  pauseSurvivalTimer(timer, 200000);
  assert.equal(resumeSurvivalTimer(timer, 200000), true);
  assert.equal(resumeSurvivalTimer(timer, 200001), false);
  assert.equal(getSurvivalElapsedMs(timer, 205000), 15000);
  finishSurvivalTimer(timer, 12000);
  assert.equal(getSurvivalElapsedMs(timer, 300000), 12000);
});
