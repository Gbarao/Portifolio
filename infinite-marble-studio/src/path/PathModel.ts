import { Box3, CatmullRomCurve3, Sphere, Vector3 } from 'three';
import { clamp, degToRad, modulo } from '../core/MathUtils';
import type { PathSettings, Vec3Like } from '../presets/PresetSchema';
import { PathFrames } from './PathFrames';

export interface PathModelOptions {
  bankAngleDeg?: number;
  frameSamples?: number;
}

export const DEFAULT_FRAME_SAMPLES = 2048;

export function toVector3(point: Vec3Like): Vector3 {
  return new Vector3(point.x, point.y, point.z);
}

/** Curva Catmull-Rom + frames + métricas derivadas. Imutável: reconstruída quando os pontos mudam. */
export class PathModel {
  readonly curve: CatmullRomCurve3;
  readonly frames: PathFrames;
  readonly closed: boolean;
  readonly length: number;
  readonly boundingBox = new Box3();
  readonly boundingSphere = new Sphere();

  constructor(
    settings: Pick<PathSettings, 'points' | 'closed' | 'curveType' | 'tension'>,
    options: PathModelOptions = {},
  ) {
    this.closed = settings.closed;
    this.curve = new CatmullRomCurve3(
      settings.points.map(toVector3),
      settings.closed,
      settings.curveType,
      settings.tension,
    );
    // Mais divisões = mapeamento u→t mais preciso = velocidade mais uniforme.
    this.curve.arcLengthDivisions = clamp(settings.points.length * 40, 1000, 8000);
    this.curve.updateArcLengths();
    this.length = this.curve.getLength();

    const samples: Vector3[] = [];
    const sampleCount = 512;
    for (let i = 0; i < sampleCount; i++) {
      samples.push(this.curve.getPointAt(i / sampleCount, new Vector3()));
    }
    this.boundingBox.setFromPoints(samples);
    this.boundingSphere.setFromPoints(samples, this.boundingBox.getCenter(new Vector3()));

    this.frames = new PathFrames(
      this.curve,
      options.frameSamples ?? DEFAULT_FRAME_SAMPLES,
      settings.closed,
      degToRad(options.bankAngleDeg ?? 0),
    );
  }

  /** Normaliza u para [0, 1): cíclico em curvas fechadas, limitado em abertas. */
  wrapU(u: number): number {
    return this.closed ? modulo(u, 1) : clamp(u, 0, 1);
  }

  getPointAt(u: number, target: Vector3): Vector3 {
    return this.curve.getPointAt(this.wrapU(u), target);
  }

  getFrameAt(u: number, outTangent: Vector3, outUp: Vector3, outSide: Vector3): void {
    this.frames.getFrame(this.wrapU(u), outTangent, outUp, outSide);
  }
}
