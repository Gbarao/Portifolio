import { clamp, degToRad, TAU } from '../../core/MathUtils';
import type { MacroCameraSettings } from '../SatisfyingSettings';

export interface MacroSubject {
  width: number;
  height: number;
  depth: number;
}

export interface MacroCameraPose {
  px: number;
  py: number;
  pz: number;
  tx: number;
  ty: number;
  tz: number;
  fov: number;
}

export function createMacroCameraPose(): MacroCameraPose {
  return { px: 0, py: 0, pz: 0, tx: 0, ty: 0, tz: 0, fov: 30 };
}

/**
 * Distância que enquadra o objeto (com folga para o bulging) na largura da imagem,
 * respeitando a margem. Para formatos verticais a largura é a dimensão limitante.
 */
export function computeMacroDistance(
  settings: MacroCameraSettings,
  subject: MacroSubject,
  aspect: number,
): number {
  if (settings.distance > 0) return settings.distance;
  const vfov = degToRad(clamp(settings.fov, 10, 90));
  const hfov = 2 * Math.atan(Math.tan(vfov / 2) * Math.max(0.1, aspect));
  const azimuth = degToRad(settings.azimuth);
  // Largura projetada da caixa vista pelo azimute + folga do bulging (~6 %).
  const projected =
    Math.abs(Math.cos(azimuth)) * subject.width + Math.abs(Math.sin(azimuth)) * subject.depth;
  const halfWidth = (projected * 1.06) / 2;
  const margin = clamp(settings.framingMargin, 0, 0.45);
  const halfVisible = halfWidth / (1 - 2 * margin);
  const byWidth = halfVisible / Math.tan(hfov / 2);
  // Altura: objeto + espaço para a ferramenta entrar por cima.
  const byHeight = (subject.height * 1.6) / Math.tan(vfov / 2);
  return Math.max(byWidth, byHeight) + 0.25 * Math.max(subject.width, subject.depth);
}

/**
 * Pose da câmera macro em t ∈ [0, 1): órbita sutil + respiro de distância com ciclos
 * inteiros — pose(0) === pose(1) por construção. Nada é acumulado.
 */
export function evaluateMacroCamera(
  settings: MacroCameraSettings,
  subject: MacroSubject,
  aspect: number,
  t: number,
  out: MacroCameraPose = createMacroCameraPose(),
): MacroCameraPose {
  const cycles = Math.max(1, Math.round(settings.cycles));
  const phase = TAU * cycles * (t - Math.floor(t));
  const baseDistance = computeMacroDistance(settings, subject, aspect);
  const distance = baseDistance * (1 + settings.dollyAmplitude * Math.sin(phase));
  const azimuth = degToRad(settings.azimuth + settings.orbitAmplitude * Math.sin(phase));
  const elevation = degToRad(
    clamp(settings.elevation + 0.35 * settings.orbitAmplitude * Math.sin(2 * phase), -10, 80),
  );
  const ty = subject.height * settings.targetHeight;
  out.tx = 0;
  out.ty = ty;
  out.tz = 0;
  out.px = distance * Math.cos(elevation) * Math.sin(azimuth);
  out.py = ty + distance * Math.sin(elevation);
  out.pz = distance * Math.cos(elevation) * Math.cos(azimuth);
  out.fov = clamp(settings.fov, 10, 90);
  return out;
}
