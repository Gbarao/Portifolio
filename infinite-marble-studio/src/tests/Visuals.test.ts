import { Sphere, Vector3 } from 'three';
import { describe, expect, it } from 'vitest';
import { computeRestHeight } from '../marbles/MarbleKinematics';
import { createPathSettings } from '../path/PathFactory';
import { PathModel } from '../path/PathModel';
import { findBuiltInPreset } from '../presets/DefaultPresets';
import { computeDecorationLayout } from '../scene/DecorationManager';
import {
  GROOVE_HALF_ANGLE_DEG,
  buildGrooveGeometry,
  buildGrooveProfile,
  grooveWallThickness,
} from '../track/GrooveTrackBuilder';
import { computeSupportLayout } from '../track/SupportBuilder';
import { trackOuterRadius } from '../track/TrackBuilder';
import { drawWoodGrain } from '../track/WoodTexture';

const model = (id: Parameters<typeof createPathSettings>[0]): PathModel =>
  new PathModel(createPathSettings(id, 1));

describe('Canaleta (groove)', () => {
  it('geometria finita, com normais unitárias coerentes com a orientação dos triângulos', () => {
    const geometry = buildGrooveGeometry(model('spiralTower'), 0.4, 120, 10);
    const pos = geometry.getAttribute('position');
    const nor = geometry.getAttribute('normal');
    const uv = geometry.getAttribute('uv');
    const index = geometry.getIndex();
    expect(index).not.toBeNull();
    const strips = buildGrooveProfile(0.4, 10);
    const perRing = strips.reduce((sum, s) => sum + s.points.length, 0);
    expect(pos.count).toBe(perRing * 121);
    for (let i = 0; i < pos.count; i++) {
      expect(Number.isFinite(pos.getX(i) + pos.getY(i) + pos.getZ(i))).toBe(true);
      const len = Math.hypot(nor.getX(i), nor.getY(i), nor.getZ(i));
      expect(len).toBeCloseTo(1, 5);
      expect(uv.getX(i)).toBeGreaterThanOrEqual(0);
      expect(uv.getX(i)).toBeLessThanOrEqual(1);
    }
    const a = new Vector3();
    const b = new Vector3();
    const c = new Vector3();
    const n = new Vector3();
    let disagree = 0;
    for (let t = 0; t < index!.count; t += 3) {
      a.fromBufferAttribute(pos, index!.getX(t));
      b.fromBufferAttribute(pos, index!.getX(t + 1));
      c.fromBufferAttribute(pos, index!.getX(t + 2));
      n.fromBufferAttribute(nor, index!.getX(t));
      const face = b.clone().sub(a).cross(c.clone().sub(a));
      if (face.lengthSq() > 1e-12 && face.dot(n) <= 0) disagree++;
    }
    expect(disagree).toBe(0);
    geometry.dispose();
  });

  it('abre para cima: normal do fundo interno aponta para o centro do canal', () => {
    const [inner] = buildGrooveProfile(0.5, 8);
    const middle = Math.floor(inner!.points.length / 2);
    expect(inner!.points[middle]![1]).toBeCloseTo(-0.5, 6);
    expect(inner!.normals[middle]![1]).toBeCloseTo(1, 6);
  });

  it('bolinha menor que o canal repousa no fundo; maior apoia nas bordas', () => {
    const track = { style: 'groove' as const, radius: 0.4, railDistance: 1, railRadius: 0.1 };
    expect(computeRestHeight(track, 0.3)).toBeCloseTo(-0.1, 9);
    const angle = (GROOVE_HALF_ANGLE_DEG * Math.PI) / 180;
    const rimX = 0.4 * Math.sin(angle);
    const rimY = -0.4 * Math.cos(angle);
    expect(computeRestHeight(track, 0.5)).toBeCloseTo(rimY + Math.sqrt(0.25 - rimX * rimX), 9);
    expect(trackOuterRadius(track)).toBeCloseTo(0.4 + grooveWallThickness(0.4), 9);
  });
});

describe('Frames alinhados à gravidade', () => {
  it.each(['coilTower', 'spiralTower', 'stackedCircuit', 'wave3d'] as const)(
    '%s mantém "para cima" sempre acima do horizonte',
    (id) => {
      const path = model(id);
      expect(path.frames.mode).toBe('gravity');
      const t = new Vector3();
      const u = new Vector3();
      const s = new Vector3();
      for (let i = 0; i < 300; i++) {
        path.getFrameAt(i / 300, t, u, s);
        expect(u.y).toBeGreaterThan(0.5);
      }
    },
  );

  it('loops verticais continuam com transporte paralelo', () => {
    expect(model('circle').frames.mode).toBe('transport');
    expect(model('sTrack').frames.mode).toBe('transport');
  });
});

describe('Hastes de suporte', () => {
  const preset = findBuiltInPreset('Blue Coaster')!;
  const path = new PathModel(preset.path);

  it('são determinísticas, vão do chão ao trilho e não atravessam outro trecho', () => {
    const a = computeSupportLayout(path, preset.track, preset.background.groundHeight);
    const b = computeSupportLayout(path, preset.track, preset.background.groundHeight);
    expect(a).toEqual(b);
    expect(a.placements.length).toBeGreaterThan(2);
    const outer = trackOuterRadius(preset.track);
    const point = new Vector3();
    for (const p of a.placements) {
      expect(p.top).toBeGreaterThan(p.bottom);
      for (let i = 0; i < 400; i++) {
        path.getPointAt(i / 400, point);
        const inColumn = Math.hypot(point.x - p.x, point.z - p.z) < outer + a.poleRadius;
        const below = point.y < p.top - outer && point.y > p.bottom;
        expect(inColumn && below).toBe(false);
      }
    }
  });

  it('não geram hastes quando o chão está acima do trilho', () => {
    const layout = computeSupportLayout(path, preset.track, 100);
    expect(layout.placements).toEqual([]);
  });
});

describe('Cúpulas decorativas', () => {
  const bounds = new Sphere(new Vector3(0, 0, 0), 5);
  it('layout determinístico pela seed e fora do centro do trajeto', () => {
    const a = computeDecorationLayout(42, bounds);
    expect(a).toEqual(computeDecorationLayout(42, bounds));
    expect(a).not.toEqual(computeDecorationLayout(43, bounds));
    for (const d of a) {
      expect(Math.hypot(d.x, d.z)).toBeGreaterThanOrEqual(5 * 0.95 - 1e-9);
      expect(d.radius).toBeGreaterThan(0);
    }
  });
});

describe('Textura de madeira', () => {
  const width = 256;
  const height = 32;
  const draw = (seed: number): Uint8ClampedArray => {
    const data = new Uint8ClampedArray(width * height * 4);
    drawWoodGrain(data, width, height, seed);
    return data;
  };

  it('é determinística e muda com a seed', () => {
    expect(draw(7)).toEqual(draw(7));
    expect(draw(7)).not.toEqual(draw(8));
  });

  it('repete sem emenda ao longo do comprimento', () => {
    const data = draw(7);
    const at = (x: number, y: number): number => data[(y * width + x) * 4] as number;
    let seam = 0;
    let neighbor = 0;
    for (let y = 0; y < height; y++) {
      seam = Math.max(seam, Math.abs(at(width - 1, y) - at(0, y)));
      for (let x = 1; x < width; x++)
        neighbor = Math.max(neighbor, Math.abs(at(x, y) - at(x - 1, y)));
    }
    expect(seam).toBeLessThanOrEqual(neighbor);
  });
});
