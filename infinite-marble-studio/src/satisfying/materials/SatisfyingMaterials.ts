import { MeshPhysicalMaterial } from 'three';
import type { SatisfyingMaterialId, SatisfyingMaterialSettings } from '../SatisfyingSettings';

/**
 * Materiais procedurais do objeto macio (sem texturas externas). Cada preset define a
 * "assinatura" física do material; a cor é escolhida à parte (seed/preset).
 */
export const SOFT_MATERIAL_PRESETS: Readonly<
  Record<
    SatisfyingMaterialId,
    Omit<SatisfyingMaterialSettings, 'type' | 'color' | 'attenuationColor'>
  >
> = {
  softRubber: {
    roughness: 0.55,
    metalness: 0,
    clearcoat: 0.25,
    clearcoatRoughness: 0.4,
    sheen: 0.5,
    sheenColor: 0xffffff,
    sheenRoughness: 0.6,
    transmission: 0,
    thickness: 1,
    specularIntensity: 0.45,
    ior: 1.5,
  },
  glossyGel: {
    roughness: 0.32,
    metalness: 0,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
    sheen: 0.35,
    sheenColor: 0xffffff,
    sheenRoughness: 0.45,
    transmission: 0,
    thickness: 1,
    specularIntensity: 0.6,
    ior: 1.45,
  },
  slime: {
    roughness: 0.12,
    metalness: 0,
    clearcoat: 1,
    clearcoatRoughness: 0.03,
    sheen: 0,
    sheenColor: 0xffffff,
    sheenRoughness: 0.5,
    transmission: 0.55,
    thickness: 1.6,
    specularIntensity: 0.9,
    ior: 1.38,
  },
  foam: {
    roughness: 0.95,
    metalness: 0,
    clearcoat: 0,
    clearcoatRoughness: 1,
    sheen: 1,
    sheenColor: 0xffffff,
    sheenRoughness: 0.9,
    transmission: 0,
    thickness: 1,
    specularIntensity: 0.15,
    ior: 1.3,
  },
  silicone: {
    roughness: 0.42,
    metalness: 0,
    clearcoat: 0.55,
    clearcoatRoughness: 0.22,
    sheen: 0.25,
    sheenColor: 0xffffff,
    sheenRoughness: 0.5,
    transmission: 0.18,
    thickness: 1.2,
    specularIntensity: 0.55,
    ior: 1.42,
  },
  wax: {
    roughness: 0.48,
    metalness: 0,
    clearcoat: 0.3,
    clearcoatRoughness: 0.35,
    sheen: 0.6,
    sheenColor: 0xfff4e0,
    sheenRoughness: 0.7,
    transmission: 0.08,
    thickness: 1.4,
    specularIntensity: 0.4,
    ior: 1.44,
  },
  softPlastic: {
    roughness: 0.38,
    metalness: 0,
    clearcoat: 0.6,
    clearcoatRoughness: 0.18,
    sheen: 0.1,
    sheenColor: 0xffffff,
    sheenRoughness: 0.4,
    transmission: 0,
    thickness: 1,
    specularIntensity: 0.55,
    ior: 1.49,
  },
  butter: {
    roughness: 0.62,
    metalness: 0,
    clearcoat: 0.15,
    clearcoatRoughness: 0.5,
    sheen: 0.7,
    sheenColor: 0xfff6d8,
    sheenRoughness: 0.75,
    transmission: 0.05,
    thickness: 1.2,
    specularIntensity: 0.35,
    ior: 1.46,
  },
  candy: {
    roughness: 0.18,
    metalness: 0,
    clearcoat: 1,
    clearcoatRoughness: 0.04,
    sheen: 0.15,
    sheenColor: 0xffffff,
    sheenRoughness: 0.3,
    transmission: 0.25,
    thickness: 1.4,
    specularIntensity: 0.8,
    ior: 1.5,
  },
};

/** Aplica a assinatura do tipo sobre as configurações, mantendo cor e tipo. */
export function withMaterialPreset(
  settings: SatisfyingMaterialSettings,
  type: SatisfyingMaterialId,
): SatisfyingMaterialSettings {
  return { ...settings, ...SOFT_MATERIAL_PRESETS[type], type };
}

export function createSoftMaterial(settings: SatisfyingMaterialSettings): MeshPhysicalMaterial {
  const material = new MeshPhysicalMaterial();
  material.name = 'soft-object';
  updateSoftMaterial(material, settings);
  return material;
}

/** Atualiza o material existente (sem recriar shader, exceto quando transmissão liga/desliga). */
export function updateSoftMaterial(
  material: MeshPhysicalMaterial,
  settings: SatisfyingMaterialSettings,
): void {
  material.color.set(settings.color);
  material.roughness = settings.roughness;
  material.metalness = settings.metalness;
  material.clearcoat = settings.clearcoat;
  material.clearcoatRoughness = settings.clearcoatRoughness;
  material.sheen = settings.sheen;
  material.sheenColor.set(settings.sheenColor);
  material.sheenRoughness = settings.sheenRoughness;
  material.transmission = settings.transmission;
  material.thickness = settings.thickness;
  material.attenuationColor.set(settings.attenuationColor);
  material.attenuationDistance = settings.transmission > 0 ? 1.2 : Infinity;
  material.specularIntensity = settings.specularIntensity;
  material.ior = settings.ior;
}
