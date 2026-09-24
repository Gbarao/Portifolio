export interface Debounced<Args extends unknown[]> {
  (...args: Args): void;
  /** Executa imediatamente a chamada pendente, se houver. */
  flush(): void;
  cancel(): void;
  readonly pending: boolean;
}

export function debounce<Args extends unknown[]>(
  fn: (...args: Args) => void,
  waitMs: number,
): Debounced<Args> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let lastArgs: Args | null = null;

  const run = (): void => {
    timer = null;
    const args = lastArgs;
    lastArgs = null;
    if (args) fn(...args);
  };

  const debounced = ((...args: Args): void => {
    lastArgs = args;
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(run, waitMs);
  }) as Debounced<Args>;

  debounced.flush = (): void => {
    if (timer === null) return;
    clearTimeout(timer);
    run();
  };

  debounced.cancel = (): void => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    lastArgs = null;
  };

  Object.defineProperty(debounced, 'pending', { get: () => timer !== null });
  return debounced;
}
