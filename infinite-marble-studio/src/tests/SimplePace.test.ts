import { describe, expect, it } from 'vitest';
import { applySimpleDuration, capturePace } from '../app/SimplePace';
import { validateExport } from '../export/ExportValidator';
import { BUILT_IN_PRESETS, createDefaultProject } from '../presets/DefaultPresets';
import { SceneEvaluator } from '../scene/SceneStateCapture';
import { END_EPSILON, maxAbsDiff } from './helpers';

describe('Duração no modo simples', () => {
  it('vídeo de 1 minuto mantém a velocidade das bolinhas com voltas inteiras', () => {
    const project = createDefaultProject();
    const pace = capturePace(project);
    applySimpleDuration(project, pace, 60);
    expect(project.loop.durationSeconds).toBe(60);
    expect(project.output.durationSeconds).toBe(60);
    // 1 volta a cada 8 s → 7,5 voltas por minuto → arredonda para 8 (inteiro).
    expect(project.marbles.cycleCount).toBe(8);
    expect(project.camera.cycleCount).toBe(1);
  });

  it('alternar durações não acumula arredondamento', () => {
    const project = createDefaultProject();
    const pace = capturePace(project);
    for (const seconds of [60, 5, 30, 8, 15, 60, 8]) applySimpleDuration(project, pace, seconds);
    expect(project.marbles.cycleCount).toBe(1);
    applySimpleDuration(project, pace, 30);
    expect(project.marbles.cycleCount).toBe(4);
  });

  it('ritmo capturado de um projeto longo equivale ao de 8 s', () => {
    const project = createDefaultProject();
    applySimpleDuration(project, capturePace(project), 60);
    const pace = capturePace(project);
    applySimpleDuration(project, pace, 8);
    expect(project.marbles.cycleCount).toBe(1);
  });

  it('câmera na pista acompanha as bolinhas', () => {
    const project = createDefaultProject();
    project.camera.mode = 'rail';
    applySimpleDuration(project, capturePace(project), 60);
    expect(project.camera.cycleCount).toBe(project.marbles.cycleCount);
  });

  it.each(BUILT_IN_PRESETS.map((p) => [p.name, p] as const))(
    '"%s" com 1 minuto: exportável (1800 frames a 30 fps) e com loop perfeito',
    (_name, preset) => {
      const project = structuredClone(preset);
      applySimpleDuration(project, capturePace(project), 60);
      const result = validateExport(project, 'video', null);
      expect(result.errors).toEqual([]);
      expect(result.plan).toMatchObject({ durationSeconds: 60, totalFrames: 1800, loopRepeats: 1 });
      const evaluator = new SceneEvaluator(project);
      const start = evaluator.capture(0);
      const end = evaluator.capture(1 - END_EPSILON);
      expect(maxAbsDiff(start.marblePositions, end.marblePositions)).toBeLessThan(0.001);
      expect(maxAbsDiff(start.cameraPosition, end.cameraPosition)).toBeLessThan(0.001);
    },
  );
});
