import {
  createClock, getActiveElapsedMs, pauseClock, resumeClock, startClock,
} from "./clock.js";

export const SURVIVAL_COUNTDOWN_MS = 3000;

export function createSurvivalTimer(nowMs) {
  return {
    phase: "countdown",
    countdownRemainingMs: SURVIVAL_COUNTDOWN_MS,
    countdownSinceMs: nowMs,
    clock: createClock(),
  };
}

export function getSurvivalCountdownMs(timer, nowMs) {
  if (timer.phase === "countdown") {
    return Math.max(0, timer.countdownRemainingMs -
      (nowMs - timer.countdownSinceMs));
  }
  return timer.countdownRemainingMs;
}

export function getSurvivalElapsedMs(timer, nowMs) {
  return getActiveElapsedMs(timer.clock, nowMs);
}

export function advanceSurvivalTimer(timer, nowMs) {
  if (timer.phase !== "countdown") {
    return false;
  }
  const countdownEndsAtMs = timer.countdownSinceMs + timer.countdownRemainingMs;
  if (nowMs < countdownEndsAtMs) {
    return false;
  }
  startClock(timer.clock, countdownEndsAtMs);
  timer.phase = "running";
  return true;
}

export function pauseSurvivalTimer(timer, nowMs) {
  advanceSurvivalTimer(timer, nowMs);
  if (timer.phase === "countdown") {
    timer.countdownRemainingMs = getSurvivalCountdownMs(timer, nowMs);
    timer.phase = "paused-countdown";
  } else if (timer.phase === "running") {
    pauseClock(timer.clock, nowMs);
    timer.phase = "paused-running";
  }
}

export function resumeSurvivalTimer(timer, nowMs) {
  if (timer.phase === "paused-countdown") {
    timer.countdownSinceMs = nowMs;
    timer.phase = "countdown";
    return true;
  }
  if (timer.phase === "paused-running") {
    resumeClock(timer.clock, nowMs);
    timer.phase = "running";
    return true;
  }
  return false;
}

export function finishSurvivalTimer(timer, fatalElapsedMs) {
  if (timer.phase !== "running") {
    return;
  }
  const deadlineMs = timer.clock.runningSinceMs +
    (fatalElapsedMs - timer.clock.elapsedBeforeRunMs);
  pauseClock(timer.clock, deadlineMs);
  timer.phase = "finished";
}
