export function createClock() {
  return {
    hasStarted: false,
    isPaused: false,
    elapsedBeforeRunMs: 0,
    runningSinceMs: null,
  };
}

export function startClock(clock, nowMs) {
  if (clock.hasStarted || clock.isPaused) {
    return false;
  }

  clock.hasStarted = true;
  clock.runningSinceMs = nowMs;
  return true;
}

export function pauseClock(clock, nowMs) {
  if (clock.isPaused) {
    return false;
  }

  if (clock.runningSinceMs !== null) {
    clock.elapsedBeforeRunMs += Math.max(0, nowMs - clock.runningSinceMs);
    clock.runningSinceMs = null;
  }

  clock.isPaused = true;
  return true;
}

export function resumeClock(clock, nowMs) {
  if (!clock.isPaused) {
    return false;
  }

  clock.isPaused = false;
  if (clock.hasStarted) {
    clock.runningSinceMs = nowMs;
  }
  return true;
}

export function getActiveElapsedMs(clock, nowMs) {
  if (clock.runningSinceMs === null) {
    return clock.elapsedBeforeRunMs;
  }

  return clock.elapsedBeforeRunMs + Math.max(0, nowMs - clock.runningSinceMs);
}
