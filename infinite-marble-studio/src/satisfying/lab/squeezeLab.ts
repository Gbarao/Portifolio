/**
 * Laboratório de validação visual (somente `npm run dev` → /lab/squeeze.html).
 * Não faz parte do build de produção. Expõe `window.squeezeLab` para capturas.
 */
import { WebGLRenderer } from 'three';
import { timeForPressure } from '../animation/PressureCurve';
import { createDefaultSatisfyingSettings, type SatisfyingSettings } from '../SatisfyingSettings';
import { SqueezeScene } from '../SqueezeScene';
import { pressureMotionFrom } from '../SqueezeSimulation';
import { SATISFYING_PRESETS, findSatisfyingPreset } from '../presets/SatisfyingPresets';

interface SqueezeLab {
  settings: SatisfyingSettings;
  seed: number;
  rebuild(settings?: SatisfyingSettings, seed?: number): void;
  renderAt(normalizedTime: number): string;
  renderPressure(fraction: number): string;
  timeForPressure(fraction: number): number;
  measureFrameMs(samples: number): number;
  presets: string[];
  loadPreset(name: string): void;
}

declare global {
  interface Window {
    squeezeLab?: SqueezeLab;
  }
}

const params = new URLSearchParams(location.search);
const width = Number(params.get('w') ?? 540);
const height = Number(params.get('h') ?? 960);
const renderer = new WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(width, height, false);
document.body.appendChild(renderer.domElement);

let settings = createDefaultSatisfyingSettings();
let seed = Number(params.get('seed') ?? 1);
let squeeze = new SqueezeScene(settings, seed);
squeeze.attachRenderer(renderer);

function render(t: number): void {
  squeeze.update(t, width / height);
  renderer.render(squeeze.scene, squeeze.camera);
}

const lab: SqueezeLab = {
  get settings() {
    return settings;
  },
  get seed() {
    return seed;
  },
  rebuild(next = settings, nextSeed = seed) {
    squeeze.dispose();
    settings = structuredClone(next);
    seed = nextSeed;
    squeeze = new SqueezeScene(settings, seed);
    squeeze.attachRenderer(renderer);
  },
  renderAt(t) {
    render(t);
    return JSON.stringify(squeeze.state.pressure);
  },
  renderPressure(fraction) {
    const t = lab.timeForPressure(fraction);
    return lab.renderAt(t);
  },
  timeForPressure(fraction) {
    return timeForPressure(fraction, settings.pressure.timing, pressureMotionFrom(settings));
  },
  presets: SATISFYING_PRESETS.map((p) => p.name),
  loadPreset(name) {
    const preset = findSatisfyingPreset(name);
    if (!preset) throw new Error(`Preset desconhecido: ${name}`);
    lab.rebuild(preset.build(), preset.seed);
  },
  measureFrameMs(samples) {
    const start = performance.now();
    for (let i = 0; i < samples; i++) squeeze.update(i / samples, width / height);
    return (performance.now() - start) / samples;
  },
};
window.squeezeLab = lab;

if (params.has('t')) {
  render(Number(params.get('t')));
} else {
  const duration = Number(params.get('duration') ?? 6) * 1000;
  const loop = (now: number): void => {
    render((now % duration) / duration);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}
