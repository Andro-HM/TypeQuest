import {
  createClock,
  getActiveElapsedMs,
  pauseClock,
  resumeClock,
  startClock,
} from "./clock.js";

export const COUNTDOWN_MS = 3000;

export function createTimeAttackTimer(durationMs, nowMs) {
  return {
    phase: "countdown",
    durationMs: durationMs,
    countdownRemainingMs: COUNTDOWN_MS,
    countdownSinceMs: nowMs,
    clock: createClock(),
  };
}

export function getCountdownRemainingMs(timer, nowMs) {
  if (timer.phase === "countdown") {
    return Math.max(0, timer.countdownRemainingMs -
      (nowMs - timer.countdownSinceMs));
  }
  return timer.countdownRemainingMs;
}

export function getTimeAttackRemainingMs(timer, nowMs) {
  return Math.max(0, timer.durationMs - getActiveElapsedMs(timer.clock, nowMs));
}

export function formatRemainingSeconds(remainingMs) {
  // Keep 0.1 s visible until the active-time deadline really arrives.
  return (Math.ceil(Math.max(0, remainingMs) / 100) / 10).toFixed(1);
}

export function advanceTimeAttackTimer(timer, nowMs) {
  let started = false;
  let finished = false;

  if (timer.phase === "countdown") {
    const countdownEndsAtMs = timer.countdownSinceMs + timer.countdownRemainingMs;
    if (nowMs >= countdownEndsAtMs) {
      timer.phase = "running";
      startClock(timer.clock, countdownEndsAtMs);
      started = true;
    }
  }

  if (timer.phase === "running" &&
      getActiveElapsedMs(timer.clock, nowMs) >= timer.durationMs) {
    const deadlineMs = timer.clock.runningSinceMs +
      (timer.durationMs - timer.clock.elapsedBeforeRunMs);
    pauseClock(timer.clock, deadlineMs);
    timer.phase = "finished";
    finished = true;
  }

  return { started: started, finished: finished };
}

export function pauseTimeAttackTimer(timer, nowMs) {
  const transition = advanceTimeAttackTimer(timer, nowMs);
  if (timer.phase === "countdown") {
    timer.countdownRemainingMs = getCountdownRemainingMs(timer, nowMs);
    timer.phase = "paused-countdown";
  } else if (timer.phase === "running") {
    pauseClock(timer.clock, nowMs);
    timer.phase = "paused-running";
  }
  return transition;
}

export function resumeTimeAttackTimer(timer, nowMs) {
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
