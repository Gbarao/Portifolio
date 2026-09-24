/** Pilha de desfazer/refazer baseada em snapshots imutáveis. */
export class History<T> {
  private readonly undoStack: T[] = [];
  private readonly redoStack: T[] = [];
  private current: T;

  constructor(
    initial: T,
    readonly limit = 50,
    private readonly equals: (a: T, b: T) => boolean = (a, b) => a === b,
  ) {
    this.current = initial;
  }

  get present(): T {
    return this.current;
  }

  get canUndo(): boolean {
    return this.undoStack.length > 0;
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0;
  }

  get undoDepth(): number {
    return this.undoStack.length;
  }

  get redoDepth(): number {
    return this.redoStack.length;
  }

  /** Registra um novo estado. Retorna false quando o estado é igual ao atual. */
  push(state: T): boolean {
    if (this.equals(state, this.current)) return false;
    this.undoStack.push(this.current);
    if (this.undoStack.length > this.limit) this.undoStack.shift();
    this.redoStack.length = 0;
    this.current = state;
    return true;
  }

  undo(): T | null {
    const previous = this.undoStack.pop();
    if (previous === undefined) return null;
    this.redoStack.push(this.current);
    this.current = previous;
    return previous;
  }

  redo(): T | null {
    const next = this.redoStack.pop();
    if (next === undefined) return null;
    this.undoStack.push(this.current);
    this.current = next;
    return next;
  }

  reset(state: T): void {
    this.undoStack.length = 0;
    this.redoStack.length = 0;
    this.current = state;
  }
}
