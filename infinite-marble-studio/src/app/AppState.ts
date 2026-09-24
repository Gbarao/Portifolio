import { createDefaultProject } from '../presets/DefaultPresets';
import type { ScenePreset } from '../presets/PresetSchema';

export type UiMode = 'simple' | 'advanced';

export interface RuntimeState {
  /** Interface simplificada (padrão) ou painel completo. */
  uiMode: UiMode;
  helpersVisible: boolean;
  guiVisible: boolean;
  editorView: boolean;
  selectedPoint: number | null;
  exporting: boolean;
  showSafeArea: boolean;
  maxPixelRatio: number;
  previewAtExportResolution: boolean;
  previewSpeed: number;
  lastVariationReport: string;
  dirtySinceSave: boolean;
}

type PlainObject = Record<string, unknown>;

const isPlainObject = (value: unknown): value is PlainObject =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/**
 * Copia `source` para `target` preservando a identidade dos objetos aninhados
 * (os controles da GUI permanecem ligados aos mesmos objetos).
 */
export function assignDeep(target: PlainObject, source: PlainObject): void {
  for (const key of Object.keys(target)) {
    if (!(key in source)) delete target[key];
  }
  for (const [key, value] of Object.entries(source)) {
    const current = target[key];
    if (isPlainObject(value) && isPlainObject(current)) {
      assignDeep(current, value);
    } else {
      target[key] = structuredClone(value);
    }
  }
}

/** Estado global da aplicação (singleton). */
export class AppState {
  private static instance: AppState | null = null;
  readonly project: ScenePreset;
  readonly runtime: RuntimeState = {
    uiMode: 'simple',
    helpersVisible: true,
    guiVisible: true,
    editorView: false,
    selectedPoint: null,
    exporting: false,
    showSafeArea: false,
    maxPixelRatio: 1,
    previewAtExportResolution: false,
    previewSpeed: 1,
    lastVariationReport: '',
    dirtySinceSave: false,
  };

  constructor(project: ScenePreset = createDefaultProject()) {
    this.project = structuredClone(project);
  }

  static get(): AppState {
    AppState.instance ??= new AppState();
    return AppState.instance;
  }

  static initialize(project: ScenePreset): AppState {
    AppState.instance = new AppState(project);
    return AppState.instance;
  }

  /** Substitui o projeto inteiro mantendo a identidade dos objetos. */
  replaceProject(next: ScenePreset): void {
    assignDeep(
      this.project as unknown as PlainObject,
      structuredClone(next) as unknown as PlainObject,
    );
  }

  snapshot(): string {
    return JSON.stringify(this.project);
  }
}
