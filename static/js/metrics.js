
 // Count entered characters and correctly matched positions.
export function countBufferMetrics(typedBuffer, target) {
  let correctPositions = 0;

  for (let index = 0; index < typedBuffer.length; index += 1) {
    if (typedBuffer[index] === target[index]) {
      correctPositions += 1;
    }
  }

  return {
    retainedEnteredCharacters: typedBuffer.length,
    opportunityPositions: typedBuffer.length,
    correctPositions: correctPositions,
  };
}


// Calculate raw WPM, accuracy, and net WPM using active typing time.
export function calculateMetrics(counts, activeElapsedMs) {
  const activeElapsedMinutes = activeElapsedMs / 60000;

  let rawWpm = 0;

  if (activeElapsedMinutes > 0) {
    rawWpm = counts.retainedEnteredCharacters / 5 / activeElapsedMinutes;
  }

  let accuracy = 0;

  if (counts.opportunityPositions > 0) {
    accuracy = counts.correctPositions / counts.opportunityPositions;
  }

  const netWpm = rawWpm * accuracy;

  return {
    retainedEnteredCharacters: counts.retainedEnteredCharacters,
    opportunityPositions: counts.opportunityPositions,
    correctPositions: counts.correctPositions,
    rawWpm: rawWpm,
    accuracy: accuracy,
    netWpm: netWpm,
  };
}
