import { CAMERA_SPECS, MARBLE_SPECS, type ScenePreset } from '../presets/PresetSchema';

/** Duração de referência dos presets built-in: o ritmo é sempre expresso por 8 s. */
export const PACE_BASE_SECONDS = 8;

/**
 * Ritmo de referência (pode ser fracionário): voltas das bolinhas e, na câmera de pista,
 * voltas da câmera a cada `PACE_BASE_SECONDS`. Nos outros modos de câmera, `cameraCycles`
 * é o número de voltas no vídeo inteiro.
 */
export interface SimplePace {
  marbleCycles: number;
  cameraCycles: number;
}

/** Extrai o ritmo do projeto atual, normalizado para a base de 8 s. */
export function capturePace(project: ScenePreset): SimplePace {
  const factor = PACE_BASE_SECONDS / project.loop.durationSeconds;
  return {
    marbleCycles: project.marbles.cycleCount * factor,
    cameraCycles:
      project.camera.mode === 'rail'
        ? project.camera.cycleCount * factor
        : project.camera.cycleCount,
  };
}

const maxOf = (spec: { kind: string; max?: number }): number => spec.max ?? 32;

const clampCycles = (value: number, max: number): number =>
  Math.min(max, Math.max(1, Math.round(value)));

/**
 * Muda a duração do vídeo (= duração do loop) preservando a velocidade das bolinhas: o número
 * de voltas é escalado e arredondado para inteiro, então o loop continua perfeito. A câmera de
 * pista acompanha as bolinhas; nos demais modos a câmera cobre o vídeo inteiro.
 */
export function applySimpleDuration(project: ScenePreset, pace: SimplePace, seconds: number): void {
  const factor = seconds / PACE_BASE_SECONDS;
  project.loop.durationSeconds = seconds;
  project.output.durationSeconds = seconds;
  project.marbles.cycleCount = clampCycles(
    pace.marbleCycles * factor,
    maxOf(MARBLE_SPECS.cycleCount),
  );
  const cameraMax = maxOf(CAMERA_SPECS.cycleCount);
  project.camera.cycleCount =
    project.camera.mode === 'rail'
      ? clampCycles(pace.cameraCycles * factor, cameraMax)
      : clampCycles(pace.cameraCycles, cameraMax);
}
