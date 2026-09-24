import { isAnimatedCameraMode } from '../camera/CameraFactory';
import { isNearlyInteger } from '../core/MathUtils';
import { validatePathPoints } from '../path/PathValidator';
import {
  MAX_EXPORT_DIMENSION,
  MAX_EXPORT_PIXELS,
  MIN_EXPORT_DIMENSION,
  type LoopSettings,
  type OutputSettings,
  type ScenePreset,
} from '../presets/PresetSchema';

export type ExportKind = 'video' | 'image';

export interface ExportCheck {
  id: string;
  label: string;
  ok: boolean;
  severity: 'error' | 'warning';
  message: string;
}

export interface ExportRuntimeState {
  helpersHidden: boolean;
  guiHidden: boolean;
  mediaRecorderSupported: boolean;
}

export interface ExportPlan {
  /** Duração efetiva do vídeo (múltiplo inteiro do loop quando autoLoop). */
  durationSeconds: number;
  /** Frames totais do vídeo. */
  totalFrames: number;
  /** Frames por loop na taxa de exportação. */
  framesPerLoop: number;
  loopRepeats: number;
}

export interface ExportValidationResult {
  ok: boolean;
  checks: ExportCheck[];
  errors: string[];
  warnings: string[];
  plan: ExportPlan;
}

export const MAX_FRAMES_PER_SECOND_OF_VIDEO = 300;

/** Com autoLoop, arredonda a duração para o múltiplo inteiro mais próximo do loop. */
export function resolveExportPlan(output: OutputSettings, loop: LoopSettings): ExportPlan {
  const loopDuration = loop.durationSeconds;
  let duration = output.durationSeconds;
  if (output.autoLoop) {
    const repeats = Math.max(1, Math.round(duration / loopDuration));
    duration = repeats * loopDuration;
    while (duration > 300 && duration - loopDuration >= loopDuration) duration -= loopDuration;
  }
  const framesPerLoop = Math.round(loopDuration * output.fps);
  const totalFrames = Math.round(duration * output.fps);
  return {
    durationSeconds: duration,
    totalFrames,
    framesPerLoop,
    loopRepeats: duration / loopDuration,
  };
}

/** Tamanho estimado do arquivo (bytes) a partir do bitrate. */
export function estimateFileSizeBytes(bitrateMbps: number, durationSeconds: number): number {
  return (bitrateMbps * 1_000_000 * durationSeconds) / 8;
}

/** Checklist pré-exportação. Qualquer erro impede a exportação. */
export function validateExport(
  project: ScenePreset,
  kind: ExportKind,
  runtime: ExportRuntimeState | null,
): ExportValidationResult {
  const checks: ExportCheck[] = [];
  const add = (
    id: string,
    label: string,
    ok: boolean,
    message: string,
    severity: 'error' | 'warning' = 'error',
  ): void => {
    checks.push({ id, label, ok, message, severity });
  };
  const { output, loop, marbles, camera, path } = project;
  const plan = resolveExportPlan(output, loop);

  add('pathClosed', 'Curva fechada', path.closed, 'A curva precisa estar fechada para exportar.');
  const pathCheck = validatePathPoints(path.points, path.closed);
  add(
    'pathValid',
    'Curva válida',
    pathCheck.valid,
    pathCheck.errors.join(' ') || 'Curva inválida.',
  );
  add(
    'marbleCycles',
    'cycleCount inteiro e positivo',
    Number.isInteger(marbles.cycleCount) &&
      marbles.cycleCount > 0 &&
      Number.isInteger(loop.cycleCount) &&
      loop.cycleCount > 0,
    'Os ciclos das bolinhas e do loop devem ser inteiros positivos.',
  );
  add(
    'cameraCycles',
    'cameraCycles inteiro e positivo',
    !isAnimatedCameraMode(camera.mode) ||
      (Number.isInteger(camera.cycleCount) && camera.cycleCount > 0),
    'Os ciclos da câmera devem ser um inteiro positivo.',
  );
  const { width, height } = output;
  const aspect = width / height;
  const resolutionOk =
    Number.isInteger(width) &&
    Number.isInteger(height) &&
    width >= MIN_EXPORT_DIMENSION &&
    height >= MIN_EXPORT_DIMENSION &&
    width <= MAX_EXPORT_DIMENSION &&
    height <= MAX_EXPORT_DIMENSION &&
    width * height <= MAX_EXPORT_PIXELS &&
    width % 2 === 0 &&
    height % 2 === 0 &&
    aspect >= 0.25 &&
    aspect <= 4;
  add(
    'resolution',
    'Resolução válida (máx. 4K)',
    resolutionOk,
    `Resolução ${width}×${height} inválida: use dimensões pares entre ${MIN_EXPORT_DIMENSION} e ${MAX_EXPORT_DIMENSION}, até 3840×2160 pixels e proporção entre 1:4 e 4:1.`,
  );

  if (kind === 'video') {
    add(
      'duration',
      'Duração válida (1–300 s)',
      plan.durationSeconds >= 1 && plan.durationSeconds <= 300,
      `Duração ${plan.durationSeconds}s fora do intervalo 1–300 s.`,
    );
    const loopFrames = loop.durationSeconds * output.fps;
    const videoFrames = plan.durationSeconds * output.fps;
    add(
      'frameGrid',
      'totalFrames inteiro',
      isNearlyInteger(loopFrames) && isNearlyInteger(videoFrames),
      `duração × fps precisa ser inteiro (loop: ${loopFrames.toFixed(2)}, vídeo: ${videoFrames.toFixed(2)}).`,
    );
    add(
      'frameLimit',
      'totalFrames dentro do limite',
      plan.totalFrames <= MAX_FRAMES_PER_SECOND_OF_VIDEO * plan.durationSeconds,
      `totalFrames (${plan.totalFrames}) excede ${MAX_FRAMES_PER_SECOND_OF_VIDEO} × duração.`,
    );
    add(
      'loopMultiple',
      'Duração múltipla do loop',
      isNearlyInteger(plan.loopRepeats, 1e-6),
      `A duração do vídeo (${plan.durationSeconds}s) não é múltipla do loop (${loop.durationSeconds}s): o vídeo não repetirá sem emenda. Ative "Auto loop".`,
      'warning',
    );
    if (runtime) {
      add(
        'recorder',
        'MediaRecorder disponível',
        runtime.mediaRecorderSupported,
        'MediaRecorder/WebM indisponível: será exportada uma sequência PNG em ZIP.',
        'warning',
      );
    }
  }

  add(
    'performance',
    'Configuração leve',
    !(marbles.count > 150 && project.lighting.shadowsEnabled),
    'Mais de 150 bolinhas com sombras: a exportação pode ficar lenta.',
    'warning',
  );

  if (runtime) {
    add(
      'helpers',
      'Helpers ocultos',
      runtime.helpersHidden,
      'Os helpers de edição não foram ocultados.',
    );
    add('gui', 'GUI oculta', runtime.guiHidden, 'A interface não foi ocultada.');
  }

  const errors = checks.filter((c) => !c.ok && c.severity === 'error').map((c) => c.message);
  const warnings = checks.filter((c) => !c.ok && c.severity === 'warning').map((c) => c.message);
  return { ok: errors.length === 0, checks, errors, warnings, plan };
}
