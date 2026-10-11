
import { getActiveElapsedMs, pauseClock } from "./clock.js";
import { calculateMetrics, countBufferMetrics } from "./metrics.js";


// Initialize a new Classic run with no completion or result.
export function createClassicRun() {
  return {
    isComplete: false,
    result: null,
  };
}


// Assign 1, 2, or 3 stars based on typing accuracy.
export function starsForAccuracy(accuracy) {
  if (accuracy >= 0.95) {
    return 3;
  }
  if (accuracy >= 0.90) {
    return 2;
  }
  return 1;
}


// Complete the level, stop the timer, and calculate the final results.
export function completeClassicRun(run, typingState, clock, nowMs) {
  if (run.isComplete || typingState.typedBuffer.length !== typingState.target.length) {
    return null;
  }

  pauseClock(clock, nowMs);
  const completionTimeMs = getActiveElapsedMs(clock, nowMs);
  const counts = countBufferMetrics(typingState.typedBuffer, typingState.target);
  const metrics = calculateMetrics(counts, completionTimeMs);

  run.isComplete = true;
  run.result = {
    rawWpm: metrics.rawWpm,
    accuracy: metrics.accuracy,
    netWpm: metrics.netWpm,
    completionTimeMs: completionTimeMs,
    starsEarned: starsForAccuracy(metrics.accuracy),
  };

  return run.result;
}
