import type { ScenePreset } from './PresetSchema';
import { deserializePreset, serializePreset, type PresetValidationResult } from './PresetValidator';

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export const STORAGE_KEYS = {
  draft: 'ims.draft.v1',
  presets: 'ims.presets.v1',
  history: 'ims.exportHistory.v1',
} as const;

/** Armazenamento em memória (fallback quando localStorage não está disponível e em testes). */
export class MemoryStorage implements KeyValueStorage {
  private readonly map = new Map<string, string>();
  getItem(key: string): string | null {
    return this.map.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.map.set(key, value);
  }
  removeItem(key: string): void {
    this.map.delete(key);
  }
}

export function getBrowserStorage(): KeyValueStorage {
  try {
    const storage = globalThis.localStorage;
    const probe = '__ims_probe__';
    storage.setItem(probe, '1');
    storage.removeItem(probe);
    return storage;
  } catch {
    return new MemoryStorage();
  }
}

function describeStorageError(error: unknown): Error {
  if (error instanceof DOMException && error.name === 'QuotaExceededError') {
    return new Error(
      'Armazenamento local cheio. Exclua presets antigos ou o histórico de exportações.',
    );
  }
  return error instanceof Error ? error : new Error(String(error));
}

/** Presets do usuário e rascunho automático no localStorage. */
export class PresetStore {
  constructor(private readonly storage: KeyValueStorage) {}

  private readPresetMap(): Record<string, string> {
    const raw = this.storage.getItem(STORAGE_KEYS.presets);
    if (!raw) return {};
    try {
      const parsed: unknown = JSON.parse(raw);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return {};
      const map: Record<string, string> = {};
      for (const [name, value] of Object.entries(parsed)) {
        if (typeof value === 'string') map[name] = value;
      }
      return map;
    } catch {
      return {};
    }
  }

  private writePresetMap(map: Record<string, string>): void {
    try {
      this.storage.setItem(STORAGE_KEYS.presets, JSON.stringify(map));
    } catch (error) {
      throw describeStorageError(error);
    }
  }

  listUserPresets(): string[] {
    return Object.keys(this.readPresetMap()).sort((a, b) => a.localeCompare(b));
  }

  saveUserPreset(preset: ScenePreset, name: string, now = Date.now()): ScenePreset {
    const trimmed = name.trim();
    if (!trimmed) throw new Error('Informe um nome para o preset.');
    if (trimmed.length > 80) throw new Error('O nome do preset deve ter até 80 caracteres.');
    const toSave: ScenePreset = { ...structuredClone(preset), name: trimmed, timestamp: now };
    const map = this.readPresetMap();
    map[trimmed] = serializePreset(toSave);
    this.writePresetMap(map);
    return toSave;
  }

  loadUserPreset(name: string): PresetValidationResult | null {
    const json = this.readPresetMap()[name];
    return json === undefined ? null : deserializePreset(json);
  }

  deleteUserPreset(name: string): boolean {
    const map = this.readPresetMap();
    if (!(name in map)) return false;
    delete map[name];
    this.writePresetMap(map);
    return true;
  }

  saveDraft(preset: ScenePreset): void {
    try {
      this.storage.setItem(STORAGE_KEYS.draft, serializePreset(preset));
    } catch (error) {
      throw describeStorageError(error);
    }
  }

  loadDraft(): PresetValidationResult | null {
    const json = this.storage.getItem(STORAGE_KEYS.draft);
    return json === null ? null : deserializePreset(json);
  }

  clearDraft(): void {
    this.storage.removeItem(STORAGE_KEYS.draft);
  }
}
