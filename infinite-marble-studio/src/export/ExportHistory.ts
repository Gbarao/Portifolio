import { STORAGE_KEYS, type KeyValueStorage } from '../presets/PresetStore';

export type ExportHistoryKind = 'video' | 'zip' | 'image';

/** Metadados de uma exportação. O arquivo em si não é armazenado (limite do localStorage). */
export interface ExportHistoryEntry {
  id: string;
  kind: ExportHistoryKind;
  fileName: string;
  width: number;
  height: number;
  fps: number;
  durationSeconds: number;
  createdAt: number;
  seed: number;
  presetName: string;
  /** Miniatura JPEG (data URL) do frame inicial. */
  thumbnail: string;
  /** Preset completo usado: permite re-renderizar o mesmo arquivo (determinismo). */
  snapshot: string;
  /** Tempo normalizado capturado (PNG). */
  normalizedTime: number;
}

export const EXPORT_HISTORY_LIMIT = 10;

function isEntry(value: unknown): value is ExportHistoryEntry {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === 'string' &&
    typeof v.fileName === 'string' &&
    typeof v.createdAt === 'number' &&
    typeof v.snapshot === 'string' &&
    (v.kind === 'video' || v.kind === 'zip' || v.kind === 'image')
  );
}

/** Histórico das últimas 10 exportações no localStorage. */
export class ExportHistory {
  private counter = 0;

  constructor(
    private readonly storage: KeyValueStorage,
    private readonly limit = EXPORT_HISTORY_LIMIT,
  ) {}

  list(): ExportHistoryEntry[] {
    const raw = this.storage.getItem(STORAGE_KEYS.history);
    if (!raw) return [];
    try {
      const parsed: unknown = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.filter(isEntry).slice(0, this.limit) : [];
    } catch {
      return [];
    }
  }

  createId(now: number): string {
    this.counter += 1;
    return `${now.toString(36)}-${this.counter}`;
  }

  add(entry: ExportHistoryEntry): ExportHistoryEntry[] {
    const entries = [entry, ...this.list().filter((e) => e.id !== entry.id)].slice(0, this.limit);
    this.write(entries);
    return entries;
  }

  remove(id: string): ExportHistoryEntry[] {
    const entries = this.list().filter((e) => e.id !== id);
    this.write(entries);
    return entries;
  }

  clear(): void {
    this.storage.removeItem(STORAGE_KEYS.history);
  }

  private write(entries: ExportHistoryEntry[]): void {
    try {
      this.storage.setItem(STORAGE_KEYS.history, JSON.stringify(entries));
    } catch {
      // Cota excedida: remove miniaturas e tenta novamente.
      const slim = entries.map((e) => ({ ...e, thumbnail: '' }));
      try {
        this.storage.setItem(STORAGE_KEYS.history, JSON.stringify(slim));
      } catch {
        throw new Error('Armazenamento local cheio: não foi possível salvar o histórico.');
      }
    }
  }
}
