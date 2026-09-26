import { describe, expect, it } from 'vitest';
import { computeTotalFrames, frameToNormalizedTime } from '../core/LoopClock';
import { SeededRandom } from '../core/SeededRandom';
import { BUILT_IN_PRESETS, createDefaultProject } from '../presets/DefaultPresets';
import { deserializePreset, serializePreset, validatePreset } from '../presets/PresetValidator';
import { computeMeshVolume } from '../satisfying/deformation/MeshNormals';
import {
  SATISFYING_PRESETS,
  createSatisfyingProject,
} from '../satisfying/presets/SatisfyingPresets';
import { batchItemName, createSqueezeBatch } from '../satisfying/presets/SqueezeBatch';
import {
  MIN_VARIATION_CATEGORIES,
  SQUEEZE_VARIATION_CATEGORIES,
  createSqueezeVariation,
  formatSqueezeVariationReport,
} from '../satisfying/presets/SqueezeVariation';
import {
  SATISFYING_SECTION_SPECS,
  validateSatisfyingSettings,
} from '../satisfying/SatisfyingSchema';
import { createDefaultSatisfyingSettings } from '../satisfying/SatisfyingSettings';
import { SqueezeScene } from '../satisfying/SqueezeScene';
import { SqueezeSimulation } from '../satisfying/SqueezeSimulation';

const ASPECT = 9 / 16;

describe('Persistência (schema retrocompatível)', () => {
  it('serialização preserva SatisfyingSettings e o gerador', () => {
    for (const definition of SATISFYING_PRESETS) {
      const project = createSatisfyingProject(definition);
      const result = deserializePreset(serializePreset(project));
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect(result.preset).toEqual(project);
        expect(result.warnings).toEqual([]);
      }
    }
  });

  it('presets antigos (sem generator/satisfying) continuam idênticos', () => {
    for (const preset of BUILT_IN_PRESETS) {
      const result = validatePreset(structuredClone(preset));
      expect(result.ok).toBe(true);
      if (result.ok) {
        expect('generator' in result.preset).toBe(false);
        expect('satisfying' in result.preset).toBe(false);
        expect(result.preset).toEqual(preset);
      }
    }
  });

  it('generator "satisfying" sem seção recebe padrão com aviso; gerador desconhecido é erro', () => {
    const project = createDefaultProject() as unknown as Record<string, unknown>;
    project.generator = 'satisfying';
    const result = validatePreset(project);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.preset.satisfying).toEqual(createDefaultSatisfyingSettings());
      expect(result.warnings).toContain('satisfying: ausente, usando valores padrão.');
    }
    project.generator = 'crushMachine';
    const bad = validatePreset(project);
    expect(bad.ok).toBe(false);
    if (!bad.ok) expect(bad.errors[0]).toMatch(/^generator:/);
  });

  it('parâmetros inválidos do squeeze são rejeitados com o caminho do campo', () => {
    const settings = createDefaultSatisfyingSettings() as unknown as Record<
      string,
      Record<string, unknown>
    >;
    settings.object!.width = 99;
    settings.material!.type = 'plutonium';
    settings.pressure!.strength = Number.NaN;
    settings.lighting!.toneMapping = 'filmic';
    settings.background!.color = 'rosa';
    const result = validateSatisfyingSettings(settings);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain(
        'satisfying.object.width: valor 99 fora do intervalo [0.6, 4].',
      );
      expect(result.errors.some((e) => e.startsWith('satisfying.material.type'))).toBe(true);
      expect(result.errors.some((e) => e.startsWith('satisfying.pressure.strength'))).toBe(true);
      expect(result.errors.some((e) => e.startsWith('satisfying.lighting.toneMapping'))).toBe(true);
      expect(result.errors.some((e) => e.startsWith('satisfying.background.color'))).toBe(true);
    }
    const timing = createDefaultSatisfyingSettings();
    timing.pressure.timing.peak = 0.1;
    expect(validateSatisfyingSettings(timing).ok).toBe(false);
    const action = { ...createDefaultSatisfyingSettings(), action: 'crush' };
    expect(validateSatisfyingSettings(action).ok).toBe(false);
    expect(validateSatisfyingSettings('texto').ok).toBe(false);
  });

  it('seções ausentes do squeeze recebem padrões (JSON parcial)', () => {
    const result = validateSatisfyingSettings({ object: createDefaultSatisfyingSettings().object });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.settings).toEqual(createDefaultSatisfyingSettings());
      expect(result.warnings.length).toBeGreaterThan(0);
    }
  });
});

describe('Presets visuais', () => {
  it('possui os 6 presets pedidos, todos válidos pelo schema', () => {
    expect(SATISFYING_PRESETS.map((p) => p.name)).toEqual([
      'Pink Slime',
      'Yellow Soft Block',
      'Blue Gel',
      'Candy Cube',
      'Dark Rubber',
      'Soft Silicone',
    ]);
    for (const p of SATISFYING_PRESETS) {
      expect(validateSatisfyingSettings(p.build()).ok).toBe(true);
    }
  });
});

describe('Nova Variação', () => {
  const base = createDefaultSatisfyingSettings();

  it('altera ≥ 3 categorias, é determinística e sempre válida', () => {
    for (let seed = 1; seed <= 60; seed++) {
      const a = createSqueezeVariation(base, seed);
      const b = createSqueezeVariation(base, seed);
      expect(a).toEqual(b);
      expect(a.categories.length).toBeGreaterThanOrEqual(MIN_VARIATION_CATEGORIES);
      expect(a.changes.length).toBe(a.categories.length);
      const check = validateSatisfyingSettings(a.settings);
      if (!check.ok) throw new Error(`seed ${seed}: ${check.errors.join('; ')}`);
    }
    expect(createSqueezeVariation(base, 1).settings).not.toEqual(
      createSqueezeVariation(base, 2).settings,
    );
  });

  it('relatório no formato VARIATION #seed / Changed', () => {
    const result = createSqueezeVariation(base, 1042, {
      categories: ['shape', 'material', 'pressure', 'camera', 'lighting'],
    });
    const report = formatSqueezeVariationReport(result);
    expect(report.startsWith('VARIATION #1042\n\nChanged:\n- ')).toBe(true);
    expect(report.split('\n- ')).toHaveLength(6);
  });

  it('iluminação escura só com fundo escuro (coerência visual)', () => {
    for (let seed = 1; seed <= 80; seed++) {
      const v = createSqueezeVariation(base, seed, { categories: SQUEEZE_VARIATION_CATEGORIES });
      const dark = ['darkPremium', 'neon', 'monochrome'].includes(v.settings.lighting.preset);
      const c = v.settings.background.color;
      const lum = 0.2126 * ((c >> 16) & 255) + 0.7152 * ((c >> 8) & 255) + 0.0722 * (c & 255);
      expect(lum < 90).toBe(dark);
    }
  });

  it('variações extremas continuam finitas, sem interpenetração e com volume estável', () => {
    for (const seed of [3, 17, 99, 512, 4096]) {
      const settings = createSqueezeVariation(base, seed, {
        categories: SQUEEZE_VARIATION_CATEGORIES,
      }).settings;
      const sim = new SqueezeSimulation(settings, seed);
      sim.deform(sim.evaluate(0, ASPECT));
      const rest = computeMeshVolume(sim.deformer.positions, sim.mesh.indices);
      let worst = 0;
      for (let i = 0; i < 24; i++) {
        const state = sim.evaluate(i / 24, ASPECT);
        sim.deform(state);
        const p = sim.deformer.positions;
        let invalid = 0;
        let inside = 0;
        for (let v = 0; v < p.length; v += 3) {
          const x = p[v] as number;
          const y = p[v + 1] as number;
          const z = p[v + 2] as number;
          if (!Number.isFinite(x + y + z)) invalid++;
          const d = Math.hypot(x - state.tool.x, y - state.tool.y, z - state.tool.z);
          if (d < state.tool.radius - 1e-4) inside++;
        }
        expect(invalid).toBe(0);
        expect(inside).toBe(0);
        const volume = computeMeshVolume(p, sim.mesh.indices);
        worst = Math.max(worst, Math.abs(volume - rest) / rest);
      }
      expect(worst).toBeLessThan(0.03);
    }
  });
});

describe('Parâmetros extremos (dentro dos limites do schema)', () => {
  it('pressão máxima/mínima não produz NaN nem infinito', () => {
    const rng = new SeededRandom(7);
    for (let trial = 0; trial < 12; trial++) {
      const s = createDefaultSatisfyingSettings();
      for (const [section, specs] of Object.entries(SATISFYING_SECTION_SPECS)) {
        const target = (s as unknown as Record<string, Record<string, unknown>>)[section]!;
        for (const [key, spec] of Object.entries(specs)) {
          if (spec.kind !== 'number' || key === 'subdivision') continue;
          target[key] = rng.nextBool() ? spec.min : spec.max;
        }
      }
      s.object.subdivision = 10;
      s.pressure.toolRadius = Math.min(s.pressure.toolRadius, s.object.width, s.object.depth);
      const sim = new SqueezeSimulation(s, trial);
      for (const t of [0, 0.3, 0.45, 0.5, 0.62, 0.7, 0.9]) {
        sim.deform(sim.evaluate(t, ASPECT));
        let invalid = 0;
        for (const value of sim.deformer.positions) if (!Number.isFinite(value)) invalid++;
        for (const value of sim.deformer.normals) if (!Number.isFinite(value)) invalid++;
        expect(invalid).toBe(0);
      }
    }
  });
});

describe('Lote (batch)', () => {
  it('seed inicial + quantidade → configurações reproduzíveis squeeze-<seed>', () => {
    const base = createSatisfyingProject(SATISFYING_PRESETS[0]!);
    const a = createSqueezeBatch(base, 1000, 50);
    const b = createSqueezeBatch(base, 1000, 50);
    expect(a.map((i) => i.name)).toEqual(
      Array.from({ length: 50 }, (_, i) => batchItemName(1000 + i)),
    );
    expect(a[0]!.name).toBe('squeeze-1000');
    expect(a[49]!.name).toBe('squeeze-1049');
    expect(serializePreset(a[7]!.project)).toBe(serializePreset(b[7]!.project));
    for (const item of a) {
      const check = validatePreset(JSON.parse(serializePreset(item.project)));
      expect(check.ok).toBe(true);
    }
    expect(createSqueezeBatch(base, 5, 0)).toHaveLength(1);
  });
});

describe('Loop e exportação', () => {
  it('duração × FPS produz frames válidos e o último frame encosta no primeiro', () => {
    const settings = createDefaultSatisfyingSettings();
    const sim = new SqueezeSimulation(settings, 1);
    for (const [seconds, fps] of [
      [5, 30],
      [8, 60],
      [60, 30],
    ] as const) {
      const total = computeTotalFrames(seconds, fps);
      expect(Number.isInteger(total)).toBe(true);
      const first = frameToNormalizedTime(0, total);
      const wrap = frameToNormalizedTime(total, total);
      expect(wrap).toBe(first);
      const last = sim.evaluate(frameToNormalizedTime(total - 1, total), ASPECT);
      expect(Number.isFinite(last.tool.y)).toBe(true);
    }
  });

  it('mesmo frame → mesmo estado (preview e export usam a mesma função)', () => {
    const settings = createDefaultSatisfyingSettings();
    const a = new SqueezeSimulation(settings, 5);
    const b = new SqueezeSimulation(settings, 5);
    const total = computeTotalFrames(6, 30);
    for (const frame of [0, 37, 90, 179]) {
      const t = frameToNormalizedTime(frame, total);
      a.deform(a.evaluate(t, ASPECT));
      // b passa por outros frames antes (ordem não pode importar: nada é acumulado).
      b.deform(b.evaluate(0.77, ASPECT));
      b.deform(b.evaluate(t, ASPECT));
      expect(b.deformer.positions).toEqual(a.deformer.positions);
    }
  });
});

describe('SqueezeScene (sem WebGL)', () => {
  it('alteração de parâmetros atualiza a cena sem reconstruir a malha', () => {
    const settings = createDefaultSatisfyingSettings();
    const scene = new SqueezeScene(structuredClone(settings), 1);
    const next = structuredClone(settings);
    next.material.color = 0x00ff00;
    next.pressure.strength = 0.2;
    next.camera.azimuth = -30;
    expect(scene.canUpdateInPlace(next, 1)).toBe(true);
    scene.applySettings(next);
    scene.update(0.5, ASPECT);
    const material = scene.scene.getObjectByName('soft-object') as unknown as {
      material: { color: { getHex(): number } };
    };
    expect(material.material.color.getHex()).toBe(0x00ff00);
    expect(scene.camera.position.x).toBeLessThan(0);
    const reshaped = structuredClone(next);
    reshaped.object.width = 3;
    expect(scene.canUpdateInPlace(reshaped, 1)).toBe(false);
    expect(scene.canUpdateInPlace(next, 2)).toBe(false);
    scene.dispose();
  });

  it('câmera, ferramenta e luzes retornam ao estado inicial em t = 1', () => {
    const scene = new SqueezeScene(createDefaultSatisfyingSettings(), 3);
    const snapshot = (): number[] => {
      const lights: number[] = [];
      scene.scene.traverse((node) => {
        const light = node as unknown as { isLight?: boolean; intensity: number };
        if (light.isLight) lights.push(light.intensity);
      });
      const tool = scene.scene.getObjectByName('pressure-tool-sphere')!;
      return [
        ...scene.camera.position.toArray(),
        ...scene.camera.quaternion.toArray(),
        ...tool.position.toArray(),
        ...lights,
      ];
    };
    scene.update(0, ASPECT);
    const start = snapshot();
    scene.update(0.5, ASPECT);
    const middle = snapshot();
    scene.update(1, ASPECT);
    expect(snapshot()).toEqual(start);
    expect(middle).not.toEqual(start);
    scene.dispose();
  });
});
