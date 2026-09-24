import { describe, expect, it } from 'vitest';
import { assignDeep } from '../app/AppState';
import {
  BUILT_IN_PRESETS,
  LIGHTING_PRESETS,
  createDefaultProject,
  findBuiltInPreset,
} from '../presets/DefaultPresets';
import { PRESET_VERSION, SECTION_SPECS } from '../presets/PresetSchema';
import { MemoryStorage, PresetStore, STORAGE_KEYS } from '../presets/PresetStore';
import {
  deserializePreset,
  migratePreset,
  serializePreset,
  validatePreset,
} from '../presets/PresetValidator';

describe('Serialização', () => {
  it('serialize → JSON → deserialize preserva todos os valores', () => {
    const project = createDefaultProject();
    project.description = 'teste';
    project.marbles.customColors = [0x123456, 0xabcdef];
    const result = deserializePreset(serializePreset(project));
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.preset).toEqual(project);
      expect(result.migratedFrom).toBeNull();
      expect(result.warnings).toEqual([]);
    }
  });

  it.each(BUILT_IN_PRESETS.map((p) => [p.name, p] as const))(
    'preset built-in "%s" é válido',
    (_n, preset) => {
      const result = validatePreset(structuredClone(preset));
      expect(result.ok).toBe(true);
    },
  );

  it('JSON inválido é rejeitado com erro claro', () => {
    const result = deserializePreset('{ "name": ');
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors[0]).toMatch(/^JSON inválido/);
    const notObject = deserializePreset('[1,2,3]');
    expect(notObject.ok).toBe(false);
  });

  it('tipos e intervalos errados geram mensagens com o caminho do campo', () => {
    const project = createDefaultProject() as unknown as Record<string, Record<string, unknown>>;
    project.marbles!.count = 500;
    project.marbles!.cycleCount = 1.5;
    project.track!.style = 'groove';
    project.lighting!.shadowsEnabled = 'sim';
    project.background!.colorMain = 'azul';
    const result = validatePreset(project);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('marbles.count: valor 500 fora do intervalo [1, 250].');
      expect(result.errors).toContain('marbles.cycleCount: esperado número inteiro, recebido 1.5.');
      expect(result.errors.some((e) => e.startsWith('track.style'))).toBe(true);
      expect(result.errors.some((e) => e.startsWith('lighting.shadowsEnabled'))).toBe(true);
      expect(result.errors.some((e) => e.startsWith('background.colorMain'))).toBe(true);
    }
  });

  it('campos obrigatórios ausentes são erros; opcionais recebem padrão com aviso', () => {
    const project = createDefaultProject() as unknown as Record<string, Record<string, unknown>>;
    delete project.marbles!.count;
    expect(validatePreset(project).ok).toBe(false);
    const project2 = createDefaultProject() as unknown as Record<string, Record<string, unknown>>;
    delete project2.marbles!.pulseAmount;
    const result = validatePreset(project2);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.preset.marbles.pulseAmount).toBe(0);
      expect(result.warnings).toContain('marbles.pulseAmount: ausente, usando valor padrão.');
    }
  });

  it('JSON apenas com os campos do schema original (obrigatórios) é aceito', () => {
    const full = createDefaultProject() as unknown as Record<string, unknown>;
    const minimal: Record<string, unknown> = {
      version: 1,
      name: 'Mínimo',
      seed: 1,
      timestamp: 0,
      path: full.path,
    };
    for (const [section, specs] of Object.entries(SECTION_SPECS)) {
      const source = full[section] as Record<string, unknown>;
      minimal[section] = Object.fromEntries(
        Object.entries(specs)
          .filter(([, spec]) => spec.required)
          .map(([key]) => [key, source[key]]),
      );
    }
    const result = validatePreset(minimal);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.preset.output.encoder).toBe('mediaRecorder');
      expect(result.preset.track.bankAngle).toBe(0);
    }
  });

  it('rejeita trajeto com pontos duplicados, poucos pontos ou resolução acima de 4K', () => {
    const dup = createDefaultProject();
    dup.path.points[1] = { ...dup.path.points[0]! };
    expect(validatePreset(dup).ok).toBe(false);
    const few = createDefaultProject();
    few.path.points = few.path.points.slice(0, 3);
    expect(validatePreset(few).ok).toBe(false);
    const big = createDefaultProject();
    big.output.width = 3840;
    big.output.height = 3840;
    const result = validatePreset(big);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors[0]).toContain('4K');
  });

  it('aceita cores em "#RRGGBB"', () => {
    const project = createDefaultProject() as unknown as Record<string, Record<string, unknown>>;
    project.track!.color = '#ff8800';
    const result = validatePreset(project);
    expect(result.ok && result.preset.track.color).toBe(0xff8800);
  });
});

describe('Migração de schema', () => {
  it('preset v0 (sem version, com aliases) é migrado para v1', () => {
    const current = createDefaultProject();
    const legacy = {
      name: 'Legado',
      seed: 7,
      path: current.path,
      track: { thickness: 0.4 },
      marbles: { quantity: 30, speed: 2 },
    };
    const result = validatePreset(legacy);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.migratedFrom).toBe(0);
      expect(result.preset.version).toBe(PRESET_VERSION);
      expect(result.preset.track.radius).toBe(0.4);
      expect(result.preset.marbles.count).toBe(30);
      expect(result.preset.marbles.cycleCount).toBe(2);
      expect(result.preset.lighting).toEqual(current.lighting);
    }
  });

  it('versão mais nova ou desconhecida é rejeitada', () => {
    expect(() => migratePreset({ version: PRESET_VERSION + 1 })).toThrow(/mais nova/);
    expect(validatePreset({ version: 'x', name: 'a' }).ok).toBe(false);
  });
});

describe('PresetStore (localStorage)', () => {
  it('salva, lista, carrega e exclui presets do usuário', () => {
    const storage = new MemoryStorage();
    const store = new PresetStore(storage);
    const project = createDefaultProject();
    const saved = store.saveUserPreset(project, '  Meu preset ', 123);
    expect(saved.name).toBe('Meu preset');
    expect(saved.timestamp).toBe(123);
    store.saveUserPreset(project, 'Alfa');
    expect(store.listUserPresets()).toEqual(['Alfa', 'Meu preset']);
    const loaded = store.loadUserPreset('Meu preset');
    expect(loaded?.ok && loaded.preset.name).toBe('Meu preset');
    expect(store.deleteUserPreset('Alfa')).toBe(true);
    expect(store.deleteUserPreset('Alfa')).toBe(false);
    expect(store.loadUserPreset('Alfa')).toBeNull();
    expect(() => store.saveUserPreset(project, '   ')).toThrow();
  });

  it('rascunho automático é restaurado', () => {
    const store = new PresetStore(new MemoryStorage());
    expect(store.loadDraft()).toBeNull();
    const project = createDefaultProject();
    project.name = 'Rascunho';
    store.saveDraft(project);
    const draft = store.loadDraft();
    expect(draft?.ok && draft.preset.name).toBe('Rascunho');
    store.clearDraft();
    expect(store.loadDraft()).toBeNull();
  });

  it('tolera armazenamento corrompido', () => {
    const storage = new MemoryStorage();
    storage.setItem(STORAGE_KEYS.presets, '{corrompido');
    expect(new PresetStore(storage).listUserPresets()).toEqual([]);
    storage.setItem(STORAGE_KEYS.draft, 'nada');
    const draft = new PresetStore(storage).loadDraft();
    expect(draft?.ok).toBe(false);
  });
});

describe('Presets padrão', () => {
  it('possui 5 presets de cena e 5 de iluminação', () => {
    expect(BUILT_IN_PRESETS.map((p) => p.name)).toEqual([
      'Mesmerizing Circle',
      'Golden Spiral',
      'Twisted Figure',
      'Dark Loop',
      'Minimalist',
    ]);
    expect(Object.keys(LIGHTING_PRESETS)).toHaveLength(5);
    for (const lighting of Object.values(LIGHTING_PRESETS)) {
      const ratio = lighting.fillLightIntensity / lighting.mainLightIntensity;
      expect(ratio).toBeGreaterThanOrEqual(0.3);
      expect(ratio).toBeLessThanOrEqual(0.5);
    }
    expect(findBuiltInPreset('Dark Loop')?.path.preset).toBe('torusKnot');
    expect(findBuiltInPreset('inexistente')).toBeUndefined();
  });

  it('projeto padrão segue os valores da especificação', () => {
    const p = createDefaultProject();
    expect(p.marbles.count).toBe(24);
    expect(p.output).toMatchObject({ width: 1080, height: 1920, fps: 30, durationSeconds: 8 });
    expect(p.path).toMatchObject({ closed: true, curveType: 'centripetal', tension: 0.5 });
    expect(p.track).toMatchObject({
      radius: 0.3,
      segmentCount: 200,
      radialSegments: 16,
      railDistance: 1,
      railRadius: 0.15,
    });
    expect(p.marbles).toMatchObject({ radius: 0.15, metalness: 0.8, roughness: 0.2 });
    expect(p.camera.fov).toBe(50);
    expect(p.lighting.toneMapping).toBe('linear');
    expect(p.lighting.exposure).toBeGreaterThanOrEqual(0.5);
  });
});

describe('AppState.assignDeep', () => {
  it('preserva a identidade dos objetos aninhados', () => {
    const target = createDefaultProject();
    const cameraRef = target.camera;
    const targetRef = target.camera.target;
    const next = createDefaultProject();
    next.camera.target.x = 3;
    next.marbles.count = 99;
    delete next.description;
    assignDeep(
      target as unknown as Record<string, unknown>,
      next as unknown as Record<string, unknown>,
    );
    expect(target.camera).toBe(cameraRef);
    expect(target.camera.target).toBe(targetRef);
    expect(target.camera.target.x).toBe(3);
    expect(target.marbles.count).toBe(99);
    expect('description' in target).toBe(false);
  });
});
