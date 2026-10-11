
  // Initialize the clock state before typing begins.
export function createClock() {
  return {
    hasStarted: false,
    isPaused: false,
    elapsedBeforeRunMs: 0,
    runningSinceMs: null,
  };
}

// Start the clock when the player begins typing.
export function startClock(clock, nowMs) {
  if (clock.hasStarted || clock.isPaused) {
    return false;
  }

  clock.hasStarted = true;
  clock.runningSinceMs = nowMs;
  return true;
}

// Pause the clock and save the elapsed active time.
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

// Resume the clock without counting the time spent paused.
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

// Return the total active elapsed time, excluding pauses.
export function getActiveElapsedMs(clock, nowMs) {
  if (clock.runningSinceMs === null) {
    return clock.elapsedBeforeRunMs;
  }

  return clock.elapsedBeforeRunMs + Math.max(0, nowMs - clock.runningSinceMs);
}
