import {
  backspace, createTypingState, moveCursorLeft, moveCursorRight, typeCharacter,
} from "./typing.js";
import { calculateMetrics, countBufferMetrics } from "./metrics.js";
import { createSurvivalStream, ensureSurvivalLength } from "./survival_stream.js";

export const SURVIVAL_WINDOW_CHARACTERS = 60;

export function survivalSpeedCps(elapsedSeconds) {
  return Math.min(1.5 + 0.5 * elapsedSeconds / 60, 4);
}

export function scrollDistance(elapsedSeconds) {
  // Integral of the speed curve, independent of animation frame timing.
  if (elapsedSeconds <= 300) {
    return 1.5 * elapsedSeconds + elapsedSeconds ** 2 / 240;
  }
  return 825 + 4 * (elapsedSeconds - 300);
}

export function timeForDistance(distance) {
  if (distance <= 825) {
    return (-360 + Math.sqrt(129600 + 960 * distance)) / 2;
  }
  return 300 + (distance - 825) / 4;
}

export function tierForElapsedMs(elapsedMs) {
  return Math.min(5, Math.floor(elapsedMs / 60000) + 1);
}

export function damageThreshold(stage) {
  return Math.max(1, 6 - stage);
}

function updateActiveTarget(run) {
  run.typingState.target = run.stream.target.slice(
    run.finalizedCount,
    run.finalizedCount + SURVIVAL_WINDOW_CHARACTERS
  );
}

export function createSurvivalRun(chunks, random = Math.random) {
  const stream = createSurvivalStream(chunks, random);
  ensureSurvivalLength(stream, SURVIVAL_WINDOW_CHARACTERS + 1, 1);
  const run = {
    stream: stream,
    finalizedCount: 0,
    finalizedEntries: [],
    finalizedEnteredCharacters: 0,
    finalizedCorrectPositions: 0,
    halfHeartUnits: 6,
    damageCounter: 0,
    damageStage: 0,
    typingState: createTypingState(""),
    isDead: false,
    deathElapsedMs: null,
  };
  // The typing state contains only the editable suffix; finalized positions
  // live solely in finalizedEntries and cannot be reached by Backspace/arrows.
  updateActiveTarget(run);
  return run;
}

export function typeSurvivalCharacter(run, character) {
  if (run.isDead || run.typingState.typedBuffer.length >= SURVIVAL_WINDOW_CHARACTERS &&
      run.typingState.cursorPosition === run.typingState.typedBuffer.length) {
    return false;
  }
  return typeCharacter(run.typingState, character);
}

export function backspaceSurvival(run) {
  return !run.isDead && backspace(run.typingState);
}

export function moveSurvivalCursorLeft(run) {
  return !run.isDead && moveCursorLeft(run.typingState);
}

export function moveSurvivalCursorRight(run) {
  return !run.isDead && moveCursorRight(run.typingState);
}

export function advanceSurvivalRun(run, activeElapsedMs) {
  if (run.isDead) {
    return false;
  }
  const crossedCount = Math.floor(scrollDistance(activeElapsedMs / 1000) + 1e-9);
  let changed = false;
  while (run.finalizedCount < crossedCount) {
    const index = run.finalizedCount;
    const crossingMs = timeForDistance(index + 1) * 1000;
    ensureSurvivalLength(run.stream, index + 1, tierForElapsedMs(crossingMs));
    const entry = run.typingState.typedBuffer.length > 0
      ? run.typingState.typedBuffer[0] : null;
    run.finalizedEntries.push(entry);
    run.finalizedCount += 1;
    changed = true;

    if (entry !== null) {
      run.finalizedEnteredCharacters += 1;
      run.typingState.typedBuffer = run.typingState.typedBuffer.slice(1);
      run.typingState.cursorPosition = Math.max(0, run.typingState.cursorPosition - 1);
    }

    const stage = Math.floor(crossingMs / 60000);
    if (stage !== run.damageStage) {
      run.damageStage = stage;
      run.damageCounter = 0;
    }
    if (entry !== null && entry === run.stream.target[index]) {
      run.finalizedCorrectPositions += 1;
    } else {
      run.damageCounter += 1;
      if (run.damageCounter >= damageThreshold(stage)) {
        run.halfHeartUnits -= 1;
        run.damageCounter = 0;
      }
    }

    if (run.halfHeartUnits === 0) {
      // A late callback may have crossed more positions; death belongs to
      // this fatal character boundary, so later positions stay untouched.
      run.isDead = true;
      run.deathElapsedMs = crossingMs;
      break;
    }
  }

  if (!run.isDead) {
    const currentStage = Math.floor(activeElapsedMs / 60000);
    if (currentStage !== run.damageStage) {
      run.damageStage = currentStage;
      run.damageCounter = 0;
    }
    ensureSurvivalLength(
      run.stream,
      run.finalizedCount + SURVIVAL_WINDOW_CHARACTERS + 1,
      tierForElapsedMs(activeElapsedMs)
    );
  }
  updateActiveTarget(run);
  return changed;
}

export function getSurvivalMetrics(run, activeElapsedMs) {
  const activeCounts = countBufferMetrics(
    run.typingState.typedBuffer, run.typingState.target
  );
  return calculateMetrics({
    retainedEnteredCharacters:
      run.finalizedEnteredCharacters + activeCounts.retainedEnteredCharacters,
    opportunityPositions: run.finalizedCount + activeCounts.opportunityPositions,
    correctPositions:
      run.finalizedCorrectPositions + activeCounts.correctPositions,
  }, run.isDead ? run.deathElapsedMs : activeElapsedMs);
}

export function getScrollFraction(run, activeElapsedMs) {
  const elapsedMs = run.isDead ? run.deathElapsedMs : activeElapsedMs;
  return Math.max(0, scrollDistance(elapsedMs / 1000) - run.finalizedCount);
}

export function getVisibleSurvivalSlots(run) {
  const slots = [];
  for (let offset = 0; offset <= SURVIVAL_WINDOW_CHARACTERS; offset += 1) {
    const index = run.finalizedCount + offset;
    const targetCharacter = run.stream.target[index] ?? " ";
    let status = "untouched";
    if (offset < run.typingState.typedBuffer.length) {
      status = run.typingState.typedBuffer[offset] === targetCharacter
        ? "correct" : "incorrect";
    }
    slots.push({
      character: targetCharacter,
      status: status,
      isCursor: offset === run.typingState.cursorPosition &&
        offset < SURVIVAL_WINDOW_CHARACTERS,
    });
  }
  return slots;
}
