export function createChunkStream(chunks, random = Math.random) {
  const stream = {
    chunks: chunks,
    random: random,
    chunkIds: [],
    target: "",
  };
  ensureStreamLength(stream, 1);
  return stream;
}

function appendShuffledCycle(stream) {
  const shuffled = [...stream.chunks];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(stream.random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
  }

  const previousId = stream.chunkIds.at(-1);
  if (previousId === shuffled[0].id && shuffled.length > 1) {
    [shuffled[0], shuffled[1]] = [shuffled[1], shuffled[0]];
  }

  const cycleText = shuffled.map((chunk) => chunk.text).join(" ");
  stream.target += (stream.target ? " " : "") + cycleText;
  stream.chunkIds.push(...shuffled.map((chunk) => chunk.id));
}

export function ensureStreamLength(stream, minimumLength) {
  while (stream.target.length < minimumLength) {
    appendShuffledCycle(stream);
  }
}
