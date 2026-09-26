import { createDefaultProject } from '../../presets/DefaultPresets';
import type { ScenePreset } from '../../presets/PresetSchema';
import { createSatisfyingLighting } from '../lighting/SatisfyingLighting';
import { withMaterialPreset } from '../materials/SatisfyingMaterials';
import {
  createDefaultSatisfyingSettings,
  type SatisfyingLightingId,
  type SatisfyingMaterialId,
  type SatisfyingSettings,
} from '../SatisfyingSettings';

/**
 * Presets visuais do Squeeze. Cada um define uma combinação coerente de forma, material,
 * pressão, deformação, luz e fundo (validada visualmente — ver .dev/VALIDATION.md).
 */
export interface SatisfyingPresetDefinition {
  name: string;
  /** Rótulo curto em português (modo simples). */
  label: string;
  /** Gradiente CSS da miniatura. */
  swatch: string;
  seed: number;
  build(): SatisfyingSettings;
}

function base(
  material: SatisfyingMaterialId,
  color: number,
  lighting: SatisfyingLightingId,
  background: number,
  floor: number,
): SatisfyingSettings {
  const s = createDefaultSatisfyingSettings();
  s.material = withMaterialPreset({ ...s.material, color, attenuationColor: color }, material);
  s.lighting = createSatisfyingLighting(lighting);
  s.background.color = background;
  s.background.floorColor = floor;
  return s;
}

export const SATISFYING_PRESETS: readonly SatisfyingPresetDefinition[] = [
  {
    name: 'Pink Slime',
    label: 'Slime Rosa',
    swatch: 'linear-gradient(160deg, #ff8fc4, #e0418a)',
    seed: 1101,
    build: () => {
      const s = base('slime', 0xff5fa8, 'pastel', 0xf3c6dc, 0xfbe4ef);
      s.object = { ...s.object, width: 2.3, height: 1.35, depth: 2.3, roundness: 0.55 };
      s.pressure = { ...s.pressure, strength: 0.46, toolRadius: 0.7, creep: 0.12 };
      s.deformation = { ...s.deformation, softness: 0.45, viscosity: 0.8, elasticity: 0.25 };
      return s;
    },
  },
  {
    name: 'Yellow Soft Block',
    label: 'Bloco Amarelo',
    swatch: 'linear-gradient(160deg, #ffe07a, #f4b400)',
    seed: 1102,
    build: () => {
      const s = base('softRubber', 0xffc53d, 'softWhite', 0xf4e2b8, 0xfbf1da);
      s.pressure = { ...s.pressure, toolFinish: 'ceramic', toolColor: 0xffffff };
      s.deformation = { ...s.deformation, elasticity: 0.6, viscosity: 0.3 };
      return s;
    },
  },
  {
    name: 'Blue Gel',
    label: 'Gel Azul',
    swatch: 'linear-gradient(160deg, #7fb5ff, #1f5fd6)',
    seed: 1103,
    build: () => {
      const s = base('glossyGel', 0x3d86ff, 'candy', 0xcfe0f7, 0xe9f1fc);
      s.material.transmission = 0.2;
      s.material.thickness = 1.4;
      s.object = { ...s.object, height: 1.6, roundness: 0.5 };
      s.pressure = { ...s.pressure, toolFinish: 'ceramic', toolColor: 0xffffff, strength: 0.4 };
      s.deformation = { ...s.deformation, elasticity: 0.9, viscosity: 0.15, softness: 0.45 };
      return s;
    },
  },
  {
    name: 'Candy Cube',
    label: 'Cubo de Bala',
    swatch: 'linear-gradient(160deg, #ff6b6b, #c21858)',
    seed: 1104,
    build: () => {
      const s = base('candy', 0xf0245e, 'candy', 0xc9efe3, 0xe6f8f1);
      s.object = { ...s.object, width: 2, height: 2, depth: 2, roundness: 0.28 };
      s.pressure = { ...s.pressure, toolFinish: 'ceramic', toolColor: 0xfffaf0, strength: 0.36 };
      s.deformation = { ...s.deformation, elasticity: 0.7, softness: 0.35, locality: 0.65 };
      s.camera = { ...s.camera, targetHeight: 0.7 };
      return s;
    },
  },
  {
    name: 'Dark Rubber',
    label: 'Borracha Escura',
    swatch: 'linear-gradient(160deg, #3a3a44, #0c0c10)',
    seed: 1105,
    build: () => {
      const s = base('softRubber', 0x1c1c22, 'darkPremium', 0x141418, 0x1d1d23);
      s.material.roughness = 0.5;
      s.material.clearcoat = 0.5;
      s.material.clearcoatRoughness = 0.22;
      // Sheen escuro: sem o véu acinzentado de um sheen branco.
      s.material.sheen = 0.2;
      s.material.sheenColor = 0x4a4a58;
      s.pressure = { ...s.pressure, toolFinish: 'satinMetal', toolColor: 0xd9dde4 };
      s.deformation = { ...s.deformation, elasticity: 0.5, viscosity: 0.4 };
      s.background.contactShadow = 0.7;
      return s;
    },
  },
  {
    name: 'Soft Silicone',
    label: 'Silicone Menta',
    swatch: 'linear-gradient(160deg, #a8f0dc, #3fbf9f)',
    seed: 1106,
    build: () => {
      const s = base('silicone', 0x6fd9bd, 'pastel', 0xdcd3f2, 0xf0ebfb);
      s.object = { ...s.object, width: 2.4, height: 1.3, depth: 2.4, roundness: 0.6 };
      s.pressure = { ...s.pressure, toolFinish: 'satinMetal', toolColor: 0xe8e2f5 };
      s.deformation = { ...s.deformation, viscosity: 0.65, elasticity: 0.35, softness: 0.4 };
      return s;
    },
  },
];

/** Projeto completo (ScenePreset) com o gerador Satisfying ativo. */
export function createSatisfyingProject(definition: SatisfyingPresetDefinition): ScenePreset {
  const project = createDefaultProject();
  project.name = definition.name;
  project.description = `Satisfying Objects · Squeeze · ${definition.label}`;
  project.seed = definition.seed;
  project.generator = 'satisfying';
  project.satisfying = definition.build();
  // Loop curto e hipnótico; export vertical 1080×1920.
  project.loop.durationSeconds = 6;
  project.output.durationSeconds = 6;
  return project;
}

export function findSatisfyingPreset(name: string): SatisfyingPresetDefinition | undefined {
  return SATISFYING_PRESETS.find((p) => p.name === name);
}
