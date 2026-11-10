/** Generateur pseudo-aleatoire deterministe (mulberry32) pour des mocks reproductibles. */
export type Random = () => number;

export function createRandom(seed: number): Random {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function randomBetween(random: Random, min: number, max: number): number {
  return min + (max - min) * random();
}

export function pickWeighted<T>(random: Random, items: readonly { value: T; weight: number }[]): T {
  const total = items.reduce((sum, item) => sum + item.weight, 0);
  let threshold = random() * total;
  for (const item of items) {
    threshold -= item.weight;
    if (threshold <= 0) {
      return item.value;
    }
  }
  const last = items[items.length - 1];
  if (!last) {
    throw new Error("pickWeighted requires at least one item");
  }
  return last.value;
}

/** Hash d'un texte en entier 32 bits, pour deriver une graine a partir d'une position. */
export function hashString(text: string): number {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
