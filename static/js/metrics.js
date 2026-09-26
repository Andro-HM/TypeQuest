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

export function calculateMetrics(counts, activeElapsedMs) {
  const activeElapsedMinutes = activeElapsedMs / 60000;
  const rawWpm = activeElapsedMinutes > 0
    ? counts.retainedEnteredCharacters / 5 / activeElapsedMinutes
    : 0;
  const accuracy = counts.opportunityPositions > 0
    ? counts.correctPositions / counts.opportunityPositions
    : 0;
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

export function countCompletedTargetWords(target, retainedCharacters) {
  let words = 0;
  const reachedTarget = target.slice(0, retainedCharacters);
  for (const character of reachedTarget) {
    if (character === " ") {
      words += 1;
    }
  }
  return words;
}
