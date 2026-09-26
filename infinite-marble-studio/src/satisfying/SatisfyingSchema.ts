import { roundTo } from '../core/MathUtils';
import { isObject, validateSection, type RawObject } from '../presets/FieldValidation';
import type { FieldSpec } from '../presets/PresetSchema';
import { validatePressureTiming, type PressureTiming } from './animation/PressureCurve';
import {
  createDefaultSatisfyingSettings,
  type DeformationSettings,
  type MacroCameraSettings,
  type PressureSettings,
  type SatisfyingBackgroundSettings,
  type SatisfyingLightingSettings,
  type SatisfyingMaterialSettings,
  type SatisfyingSettings,
  type SoftObjectSettings,
} from './SatisfyingSettings';

/**
 * Especificação dos campos do Satisfying Objects: fonte única para validação (JSON,
 * presets, variações) e para os limites dos controles da UI.
 */
type SpecsFor<T> = { [K in keyof T]-?: FieldSpec };

export const MATERIAL_TYPES = [
  'softRubber',
  'glossyGel',
  'slime',
  'foam',
  'silicone',
  'wax',
  'softPlastic',
  'butter',
  'candy',
] as const;

export const LIGHTING_IDS = [
  'cleanStudio',
  'softWhite',
  'pastel',
  'candy',
  'darkPremium',
  'neon',
  'warmProduct',
  'monochrome',
] as const;

export const TOOL_FINISHES = ['chrome', 'satinMetal', 'ceramic', 'glass'] as const;

export const OBJECT_SPECS: SpecsFor<SoftObjectSettings> = {
  shape: { kind: 'enum', values: ['softBlock'], required: true },
  width: { kind: 'number', min: 0.6, max: 4, step: 0.05, required: true },
  height: { kind: 'number', min: 0.5, max: 3, step: 0.05, required: true },
  depth: { kind: 'number', min: 0.6, max: 4, step: 0.05, required: true },
  roundness: { kind: 'number', min: 0.02, max: 1.2, step: 0.01, required: true },
  subdivision: { kind: 'number', min: 8, max: 48, step: 1, integer: true, required: true },
};

export const MATERIAL_SPECS: SpecsFor<SatisfyingMaterialSettings> = {
  type: { kind: 'enum', values: MATERIAL_TYPES, required: true },
  color: { kind: 'color', required: true },
  roughness: { kind: 'number', min: 0, max: 1, step: 0.01 },
  metalness: { kind: 'number', min: 0, max: 1, step: 0.01 },
  clearcoat: { kind: 'number', min: 0, max: 1, step: 0.01 },
  clearcoatRoughness: { kind: 'number', min: 0, max: 1, step: 0.01 },
  sheen: { kind: 'number', min: 0, max: 1, step: 0.01 },
  sheenColor: { kind: 'color' },
  sheenRoughness: { kind: 'number', min: 0, max: 1, step: 0.01 },
  transmission: { kind: 'number', min: 0, max: 1, step: 0.01 },
  thickness: { kind: 'number', min: 0, max: 5, step: 0.05 },
  attenuationColor: { kind: 'color' },
  specularIntensity: { kind: 'number', min: 0, max: 1, step: 0.01 },
  ior: { kind: 'number', min: 1, max: 2.333, step: 0.01 },
};

export const PRESSURE_SPECS: SpecsFor<Omit<PressureSettings, 'timing'>> = {
  tool: { kind: 'enum', values: ['sphere'], required: true },
  toolRadius: { kind: 'number', min: 0.15, max: 1.5, step: 0.01, required: true },
  toolFinish: { kind: 'enum', values: TOOL_FINISHES },
  toolColor: { kind: 'color' },
  strength: { kind: 'number', min: 0, max: 0.6, step: 0.01, required: true },
  approachHeight: { kind: 'number', min: 0.2, max: 5, step: 0.05 },
  offsetX: { kind: 'number', min: -0.6, max: 0.6, step: 0.01 },
  offsetZ: { kind: 'number', min: -0.6, max: 0.6, step: 0.01 },
  cycles: { kind: 'number', min: 1, max: 16, step: 1, integer: true },
  creep: { kind: 'number', min: 0, max: 0.3, step: 0.01 },
};

export const TIMING_SPECS: SpecsFor<PressureTiming> = {
  approachStart: { kind: 'number', min: 0, max: 1, step: 0.01 },
  contact: { kind: 'number', min: 0, max: 1, step: 0.01 },
  peak: { kind: 'number', min: 0, max: 1, step: 0.01 },
  holdEnd: { kind: 'number', min: 0, max: 1, step: 0.01 },
  toolReleaseEnd: { kind: 'number', min: 0, max: 1, step: 0.01 },
  recoveryEnd: { kind: 'number', min: 0, max: 1, step: 0.01 },
};

export const DEFORMATION_SPECS: SpecsFor<DeformationSettings> = {
  softness: { kind: 'number', min: 0, max: 0.9, step: 0.01 },
  viscosity: { kind: 'number', min: 0, max: 1, step: 0.01 },
  elasticity: { kind: 'number', min: 0, max: 1, step: 0.01 },
  bulge: { kind: 'number', min: 0, max: 2, step: 0.01 },
  volumePreservation: { kind: 'number', min: 0, max: 1.5, step: 0.01 },
  falloff: { kind: 'number', min: 0.05, max: 2, step: 0.01 },
  locality: { kind: 'number', min: 0, max: 1, step: 0.01 },
  bulgeHeight: { kind: 'number', min: 0.2, max: 0.85, step: 0.01 },
};

export const CAMERA_SPECS: SpecsFor<MacroCameraSettings> = {
  fov: { kind: 'number', min: 10, max: 75, step: 1 },
  distance: { kind: 'number', min: 0, max: 60, step: 0.1 },
  elevation: { kind: 'number', min: -5, max: 75, step: 0.5 },
  azimuth: { kind: 'number', min: -180, max: 180, step: 1 },
  targetHeight: { kind: 'number', min: 0, max: 2, step: 0.01 },
  orbitAmplitude: { kind: 'number', min: 0, max: 30, step: 0.5 },
  dollyAmplitude: { kind: 'number', min: 0, max: 0.2, step: 0.005 },
  cycles: { kind: 'number', min: 1, max: 16, step: 1, integer: true },
  framingMargin: { kind: 'number', min: 0, max: 0.4, step: 0.01 },
};

export const LIGHTING_SPECS: SpecsFor<SatisfyingLightingSettings> = {
  preset: { kind: 'enum', values: LIGHTING_IDS },
  intensity: { kind: 'number', min: 0, max: 3, step: 0.01 },
  exposure: { kind: 'number', min: 0.2, max: 3, step: 0.01 },
  key: { kind: 'number', min: 0, max: 8, step: 0.05 },
  fill: { kind: 'number', min: 0, max: 5, step: 0.05 },
  rim: { kind: 'number', min: 0, max: 8, step: 0.05 },
  top: { kind: 'number', min: 0, max: 6, step: 0.05 },
  environment: { kind: 'number', min: 0, max: 2, step: 0.01 },
  ambient: { kind: 'number', min: 0, max: 2, step: 0.01 },
  shadowSoftness: { kind: 'number', min: 1, max: 20, step: 0.5 },
  toneMapping: { kind: 'enum', values: ['neutral', 'agx', 'aces'] },
  keyColor: { kind: 'color' },
  rimColor: { kind: 'color' },
};

export const BACKGROUND_SPECS: SpecsFor<SatisfyingBackgroundSettings> = {
  color: { kind: 'color', required: true },
  floorColor: { kind: 'color' },
  contactShadow: { kind: 'number', min: 0, max: 1, step: 0.01 },
};

export const SATISFYING_SECTION_SPECS = {
  object: OBJECT_SPECS,
  material: MATERIAL_SPECS,
  pressure: PRESSURE_SPECS,
  deformation: DEFORMATION_SPECS,
  camera: CAMERA_SPECS,
  lighting: LIGHTING_SPECS,
  background: BACKGROUND_SPECS,
} as const;

export type SatisfyingSectionKey = keyof typeof SATISFYING_SECTION_SPECS;

export type SatisfyingValidationResult =
  { ok: true; settings: SatisfyingSettings; warnings: string[] } | { ok: false; errors: string[] };

/**
 * Valida um objeto desconhecido como SatisfyingSettings. Campos opcionais ausentes
 * recebem o padrão (com aviso); inválidos geram erro com o caminho do campo.
 */
export function validateSatisfyingSettings(
  input: unknown,
  prefix = 'satisfying',
): SatisfyingValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  if (!isObject(input)) {
    return { ok: false, errors: [`${prefix}: esperado objeto com as configurações.`] };
  }
  const defaults = createDefaultSatisfyingSettings() as unknown as RawObject;
  if (input.action !== undefined && input.action !== 'squeeze') {
    errors.push(
      `${prefix}.action: ação ${String(input.action)} ainda não implementada (use squeeze).`,
    );
  }
  const sections: RawObject = {};
  for (const [section, specs] of Object.entries(SATISFYING_SECTION_SPECS)) {
    const raw = input[section];
    const sectionDefaults = defaults[section] as RawObject;
    if (raw === undefined) {
      sections[section] = structuredClone(sectionDefaults);
      warnings.push(`${prefix}.${section}: ausente, usando valores padrão.`);
      continue;
    }
    sections[section] = validateSection(
      raw,
      specs as Record<string, FieldSpec>,
      sectionDefaults,
      `${prefix}.${section}`,
      errors,
      warnings,
    );
  }
  const pressureRaw = isObject(input.pressure) ? input.pressure : {};
  const timingDefaults = (defaults.pressure as RawObject).timing as RawObject;
  const timing =
    pressureRaw.timing === undefined
      ? structuredClone(timingDefaults)
      : validateSection(
          pressureRaw.timing,
          TIMING_SPECS as Record<string, FieldSpec>,
          timingDefaults,
          `${prefix}.pressure.timing`,
          errors,
          warnings,
        );
  if (errors.length === 0) {
    errors.push(
      ...validatePressureTiming(timing as unknown as PressureTiming).map(
        (e) => `${prefix}.pressure.${e}`,
      ),
    );
    const object = sections.object as unknown as SoftObjectSettings;
    const pressure = sections.pressure as unknown as PressureSettings;
    if (pressure.toolRadius > Math.max(object.width, object.depth)) {
      errors.push(`${prefix}.pressure.toolRadius: ferramenta maior que o objeto.`);
    }
  }
  if (errors.length > 0) return { ok: false, errors };
  (sections.pressure as RawObject).timing = timing;
  return {
    ok: true,
    settings: { action: 'squeeze', ...sections } as unknown as SatisfyingSettings,
    warnings,
  };
}

/** Arredonda números para JSON estável (3 casas), preservando inteiros e cores. */
export function roundSatisfyingSettings(settings: SatisfyingSettings): SatisfyingSettings {
  const round = (value: unknown): unknown => {
    if (typeof value === 'number') return Number.isInteger(value) ? value : roundTo(value, 3);
    if (isObject(value)) {
      const out: RawObject = {};
      for (const [k, v] of Object.entries(value)) out[k] = round(v);
      return out;
    }
    return value;
  };
  return round(settings) as SatisfyingSettings;
}
