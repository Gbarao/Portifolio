import { describe, expect, it } from 'vitest';
import { LoopClock } from '../core/LoopClock';
import { createPresetPoints, randomizePath } from '../path/PathFactory';
import { BUILT_IN_PRESETS, createDefaultProject } from '../presets/DefaultPresets';
import {
  ALL_VARIATION_CATEGORIES,
  APPEARANCE_CATEGORIES,
  OVERVIEW_CAMERA_MODES,
  createVariation,
  suggestCameraElevation,
  formatVariationReport,
} from '../presets/VariationGenerator';
import { SceneEvaluator, captureSceneState } from '../scene/SceneStateCapture';

describe('Determinismo com seed', () => {
  it('mesma seed e mesmas configurações produzem a mesma sequência de pontos', () => {
    expect(randomizePath(20240611).points).toEqual(randomizePath(20240611).points);
  });

  it('mesmo projeto produz exatamente o mesmo estado de cena', () => {
    const project = createDefaultProject();
    for (const t of [0, 0.123, 0.5, 0.999]) {
      expect(captureSceneState(project, t)).toEqual(captureSceneState(structuredClone(project), t));
    }
  });

  it('mesma seed produz as mesmas cores; seeds diferentes produzem cores diferentes', () => {
    const a = createDefaultProject();
    const b = createDefaultProject();
    b.seed = a.seed + 1;
    expect(captureSceneState(a, 0).marbleColors).toEqual(
      captureSceneState(structuredClone(a), 0).marbleColors,
    );
    expect(captureSceneState(a, 0).marbleColors).not.toEqual(captureSceneState(b, 0).marbleColors);
  });

  it('seed muda escalas e balanço de câmera de forma reprodutível', () => {
    const a = createDefaultProject();
    a.marbles.scaleVariation = 0.1;
    a.camera.swayAmount = 0.5;
    const b = structuredClone(a);
    b.seed = 999;
    const sa = captureSceneState(a, 0.3);
    expect(sa.marbleScales).toEqual(captureSceneState(structuredClone(a), 0.3).marbleScales);
    expect(sa.marbleScales).not.toEqual(captureSceneState(b, 0.3).marbleScales);
    expect(sa.cameraPosition).not.toEqual(captureSceneState(b, 0.3).cameraPosition);
  });

  it('preview (tempo real) e export (frame a frame) produzem estados idênticos', () => {
    const project = createDefaultProject();
    const evaluator = new SceneEvaluator(project);
    const fps = project.loop.fps;
    for (const k of [0, 17, 250, 479]) {
      let now = 0;
      const preview = new LoopClock({
        durationSeconds: project.loop.durationSeconds,
        fps,
        now: () => now,
      });
      now = (k / fps) * 1000 + 3;
      const exporter = new LoopClock({ durationSeconds: project.loop.durationSeconds, fps });
      exporter.beginExport(fps);
      exporter.setFrameIndex(k);
      const tPreview = preview.getNormalizedTime();
      const tExport = exporter.getNormalizedTime();
      expect(tPreview).toBe(tExport);
      expect(evaluator.capture(tPreview)).toEqual(evaluator.capture(tExport));
    }
  });

  it('presets built-in são determinísticos', () => {
    for (const preset of BUILT_IN_PRESETS) {
      expect(captureSceneState(preset, 0.61)).toEqual(
        captureSceneState(structuredClone(preset), 0.61),
      );
    }
  });
});

describe('Variações criativas', () => {
  it('são determinísticas para a mesma seed e projeto', () => {
    const base = createDefaultProject();
    expect(createVariation(base, 4242)).toEqual(createVariation(base, 4242));
  });

  it('alteram pelo menos 3 categorias e geram relatório', () => {
    const base = createDefaultProject();
    for (let seed = 1; seed < 40; seed++) {
      const result = createVariation(base, seed * 101);
      expect(result.categories.length).toBeGreaterThanOrEqual(3);
      expect(new Set(result.categories).size).toBe(result.categories.length);
      expect(result.changes).toHaveLength(result.categories.length);
      expect(result.project.seed).toBe(seed * 101);
      expect(result.project).not.toEqual(base);
    }
    const report = formatVariationReport(['Trajeto: Círculo → Figura de oito']);
    expect(report).toBe('Mudanças realizadas:\n- Trajeto: Círculo → Figura de oito');
  });

  it('cada categoria produz mudança real e visível', () => {
    const base = createDefaultProject();
    const result = createVariation(base, 77, { categories: ALL_VARIATION_CATEGORIES });
    const p = result.project;
    expect(p.path.preset).not.toBe(base.path.preset);
    expect(p.marbles.count).not.toBe(base.marbles.count);
    expect(p.marbles.palette).not.toBe(base.marbles.palette);
    expect(p.camera.mode).not.toBe(base.camera.mode);
    expect(p.lighting.preset).not.toBe(base.lighting.preset);
    expect(p.marbles.cycleCount).not.toBe(base.marbles.cycleCount);
    expect(p.background.colorMain).not.toBe(base.background.colorMain);
    expect(result.changes).toHaveLength(8);
  });

  it('restringe o sorteio de câmera aos modos permitidos', () => {
    const base = createDefaultProject();
    for (let seed = 1; seed <= 40; seed++) {
      const { project } = createVariation(base, seed, {
        categories: ['camera'],
        cameraModes: OVERVIEW_CAMERA_MODES,
      });
      expect(OVERVIEW_CAMERA_MODES).toContain(project.camera.mode);
    }
  });

  it('elevação da câmera sorteada acompanha o formato do trajeto', () => {
    expect(suggestCameraElevation(createPresetPoints('wave3d'))).toBe(42);
    expect(suggestCameraElevation(createPresetPoints('circle'))).toBe(28);
    expect(suggestCameraElevation(createPresetPoints('sTrack'))).toBe(14);
    const base = createDefaultProject();
    for (let seed = 1; seed <= 20; seed++) {
      const { project } = createVariation(base, seed, { categories: ['path', 'camera'] });
      const { x, y, z } = project.camera.position;
      const elevation = (Math.atan2(y, Math.hypot(x, z)) * 180) / Math.PI;
      const expected = suggestCameraElevation(project.path.points);
      expect(Math.abs(elevation - expected)).toBeLessThanOrEqual(5.1);
    }
  });

  it('randomizar aparência não altera o trajeto', () => {
    const base = createDefaultProject();
    const result = createVariation(base, 5, { categories: APPEARANCE_CATEGORIES });
    expect(result.project.path).toEqual(base.path);
  });

  it('randomizar trajeto gera percurso aleatório a partir da seed', () => {
    const base = createDefaultProject();
    const result = createVariation(base, 31337, { categories: ['path'], forceRandomPath: true });
    expect(result.project.path.preset).toBe('custom');
    expect(result.project.path.points).toEqual(randomizePath(31337).points);
  });

  it('variações produzem cenas com loop perfeito', () => {
    const base = createDefaultProject();
    for (const seed of [11, 22, 33]) {
      const { project } = createVariation(base, seed, { categories: ALL_VARIATION_CATEGORIES });
      const evaluator = new SceneEvaluator(project);
      const a = evaluator.capture(0);
      const b = evaluator.capture(1 - 1e-6);
      for (let i = 0; i < a.marblePositions.length; i++) {
        expect(Math.abs(a.marblePositions[i]! - b.marblePositions[i]!)).toBeLessThan(0.001);
      }
    }
  });
});
