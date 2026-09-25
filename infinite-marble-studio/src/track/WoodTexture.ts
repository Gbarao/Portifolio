import { CanvasTexture, ClampToEdgeWrapping, RepeatWrapping, SRGBColorSpace } from 'three';
import { PeriodicNoise } from '../core/PeriodicNoise';
import { deriveSeed } from '../core/SeededRandom';

export const WOOD_TEXTURE_WIDTH = 1024;
export const WOOD_TEXTURE_HEIGHT = 256;

/**
 * Desenha veios de madeira em RGBA (tons claros, levemente quentes; a cor final vem do
 * material). Periódico no eixo x (comprimento do trilho): a textura repete sem emenda.
 */
export function drawWoodGrain(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  seed: number,
): void {
  const warpA = new PeriodicNoise(deriveSeed(seed, 'woodA'), 5);
  const warpB = new PeriodicNoise(deriveSeed(seed, 'woodB'), 9);
  const fibers = new PeriodicNoise(deriveSeed(seed, 'woodFibers'), 64);
  const rings = 5;
  for (let y = 0; y < height; y++) {
    const fy = y / height;
    for (let x = 0; x < width; x++) {
      const fx = x / width;
      // Distorção suave: veios longos acompanhando o comprimento do trilho.
      const warp = 0.35 * warpA.sample(fx + 0.12 * fy) + 0.12 * warpB.sample(2 * fx + 0.5 * fy);
      const r = fy * rings + warp;
      const ring = r - Math.floor(r);
      const edge = Math.abs(ring - 0.5) * 2;
      const band = edge > 0.72 ? ((edge - 0.72) / 0.28) ** 1.6 : 0;
      const fiber = fibers.sample(8 * fx + 13 * fy);
      const v = 0.9 - 0.17 * band - 0.02 * fiber + 0.05 * (1 - edge);
      const o = (y * width + x) * 4;
      data[o] = Math.min(255, v * 255);
      data[o + 1] = Math.min(255, v * 0.93 * 255);
      data[o + 2] = Math.min(255, v * 0.84 * 255);
      data[o + 3] = 255;
    }
  }
}

/** Textura de madeira (DOM). Retorna null fora do navegador. */
export function createWoodTexture(seed: number): CanvasTexture | null {
  if (typeof document === 'undefined') return null;
  const canvas = document.createElement('canvas');
  canvas.width = WOOD_TEXTURE_WIDTH;
  canvas.height = WOOD_TEXTURE_HEIGHT;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  const image = ctx.createImageData(canvas.width, canvas.height);
  drawWoodGrain(image.data, canvas.width, canvas.height, seed);
  ctx.putImageData(image, 0, 0);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.wrapS = RepeatWrapping;
  texture.wrapT = ClampToEdgeWrapping;
  texture.anisotropy = 8;
  return texture;
}

/** Repetições inteiras da textura ao longo do trilho (~1 a cada 6 unidades de comprimento). */
export function woodRepeatsFor(pathLength: number): number {
  return Math.max(1, Math.round(pathLength / 6));
}
