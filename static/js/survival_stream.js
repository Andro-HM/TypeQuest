export const CHUNKS_PER_TIER = 20;

export function createSurvivalStream(chunks, random = Math.random) {
  const chunksByTier = new Map();
  for (let tier = 1; tier <= 5; tier += 1) {
    const tierChunks = chunks.filter((chunk) => chunk.tier === tier);
    if (tierChunks.length !== CHUNKS_PER_TIER) {
      throw new Error("Survival needs 20 local chunks in each tier.");
    }
    chunksByTier.set(tier, tierChunks);
  }
  return {
    chunksByTier: chunksByTier,
    random: random,
    remainingByTier: new Map(),
    lastIdByTier: new Map(),
    chunkIds: [],
    target: "",
  };
}

function shuffleTier(stream, tier) {
  const shuffled = [...stream.chunksByTier.get(tier)];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(stream.random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
  }
  if (shuffled[0].id === stream.lastIdByTier.get(tier)) {
    [shuffled[0], shuffled[1]] = [shuffled[1], shuffled[0]];
  }
  return shuffled;
}

export function ensureSurvivalLength(stream, minimumLength, tier) {
  if (!stream.chunksByTier.has(tier)) {
    throw new Error("Invalid Survival content tier.");
  }
  while (stream.target.length < minimumLength) {
    let remaining = stream.remainingByTier.get(tier);
    if (!remaining || remaining.length === 0) {
      remaining = shuffleTier(stream, tier);
      stream.remainingByTier.set(tier, remaining);
    }
    const chunk = remaining.shift();
    stream.target += (stream.target ? " " : "") + chunk.text;
    stream.chunkIds.push(chunk.id);
    stream.lastIdByTier.set(tier, chunk.id);
  }
}
