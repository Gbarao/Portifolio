import { normalizeSeed } from '../core/SeededRandom';
import { checkField, describe, isObject, validateSection, type RawObject } from './FieldValidation';
import { validatePathPoints } from '../path/PathValidator';
import { validateSatisfyingSettings } from '../satisfying/SatisfyingSchema';
import {
  createDefaultSatisfyingSettings,
  type SatisfyingSettings,
} from '../satisfying/SatisfyingSettings';
import { createDefaultProject } from './DefaultPresets';
import {
  MAX_EXPORT_PIXELS,
  MAX_PATH_POINTS,
  GENERATOR_IDS,
  MIN_PATH_POINTS,
  PATH_SPECS,
  POINT_COORD_LIMIT,
  PRESET_VERSION,
  SECTION_SPECS,
  type FieldSpec,
  type GeneratorId,
  type ScenePreset,
  type Vec3Like,
} from './PresetSchema';

export type PresetValidationResult =
  | { ok: true; preset: ScenePreset; warnings: string[]; migratedFrom: number | null }
  | { ok: false; errors: string[] };

function validatePoints(raw: unknown, errors: string[]): Vec3Like[] {
  if (!Array.isArray(raw)) {
    errors.push('path.points: esperado lista de pontos {x, y, z}.');
    return [];
  }
  if (raw.length < MIN_PATH_POINTS || raw.length > MAX_PATH_POINTS) {
    errors.push(
      `path.points: esperado entre ${MIN_PATH_POINTS} e ${MAX_PATH_POINTS} pontos, recebido ${raw.length}.`,
    );
  }
  const spec: FieldSpec = { kind: 'vec3', min: -POINT_COORD_LIMIT, max: POINT_COORD_LIMIT };
  const points: Vec3Like[] = [];
  raw.forEach((item, i) => {
    const point = checkField(spec, item, `path.points[${i}]`, errors);
    if (point) points.push(point as Vec3Like);
  });
  return points;
}

/**
 * Migração de schema. Formato v0 (sem campo `version`): seções podem faltar e usa os aliases
 * `track.thickness` (→ radius), `marbles.quantity` (→ count) e `marbles.speed` (→ cycleCount).
 */
export function migratePreset(raw: RawObject): { data: RawObject; migratedFrom: number | null } {
  const version = raw.version;
  if (typeof version === 'number' && version === PRESET_VERSION) {
    return { data: raw, migratedFrom: null };
  }
  if (typeof version === 'number' && version > PRESET_VERSION) {
    throw new Error(
      `Preset criado por uma versão mais nova do schema (v${version}); esta aplicação suporta até v${PRESET_VERSION}.`,
    );
  }
  if (version !== undefined && version !== 0) {
    throw new Error(`Versão de schema desconhecida: ${describe(version)}.`);
  }
  const defaults = createDefaultProject() as unknown as RawObject;
  const data: RawObject = structuredClone(raw);
  for (const section of Object.keys(SECTION_SPECS)) {
    const provided = isObject(data[section]) ? data[section] : {};
    data[section] = { ...(defaults[section] as RawObject), ...provided };
  }
  const track = data.track as RawObject;
  if (track.thickness !== undefined && raw.track && !(raw.track as RawObject).radius) {
    track.radius = track.thickness;
  }
  delete track.thickness;
  const marbles = data.marbles as RawObject;
  if (marbles.quantity !== undefined) marbles.count = marbles.quantity;
  if (marbles.speed !== undefined) marbles.cycleCount = marbles.speed;
  delete marbles.quantity;
  delete marbles.speed;
  if (!isObject(data.path)) data.path = defaults.path;
  data.version = PRESET_VERSION;
  return { data, migratedFrom: 0 };
}

/** Valida (e migra, se necessário) um objeto desconhecido como ScenePreset. */
export function validatePreset(input: unknown): PresetValidationResult {
  if (!isObject(input)) {
    return { ok: false, errors: ['O arquivo não contém um objeto de preset.'] };
  }
  let migrated: { data: RawObject; migratedFrom: number | null };
  try {
    migrated = migratePreset(input);
  } catch (error) {
    return { ok: false, errors: [error instanceof Error ? error.message : String(error)] };
  }
  const raw = migrated.data;
  const errors: string[] = [];
  const warnings: string[] = [];
  const defaults = createDefaultProject() as unknown as RawObject;

  if (typeof raw.name !== 'string' || raw.name.trim().length === 0 || raw.name.length > 80) {
    errors.push('name: esperado texto não vazio com até 80 caracteres.');
  }
  if (raw.description !== undefined && typeof raw.description !== 'string') {
    errors.push('description: esperado texto.');
  }
  if (typeof raw.seed !== 'number' || !Number.isFinite(raw.seed)) {
    errors.push(`seed: esperado número, recebido ${describe(raw.seed)}.`);
  }
  if (
    raw.timestamp !== undefined &&
    (typeof raw.timestamp !== 'number' || !Number.isFinite(raw.timestamp))
  ) {
    errors.push('timestamp: esperado número.');
  }

  const sections: RawObject = {};
  for (const [section, specs] of Object.entries(SECTION_SPECS)) {
    sections[section] = validateSection(
      raw[section],
      specs as Record<string, FieldSpec>,
      defaults[section] as RawObject,
      section,
      errors,
      warnings,
    );
  }

  const pathRaw = raw.path;
  const path = validateSection(
    pathRaw,
    PATH_SPECS as Record<string, FieldSpec>,
    defaults.path as RawObject,
    'path',
    errors,
    warnings,
  );
  path.points = validatePoints(isObject(pathRaw) ? pathRaw.points : undefined, errors);

  if (errors.length === 0) {
    const pathCheck = validatePathPoints(path.points as Vec3Like[], path.closed as boolean);
    errors.push(...pathCheck.errors.map((e) => `path: ${e}`));
    warnings.push(...pathCheck.warnings.map((w) => `path: ${w}`));
    const output = sections.output as RawObject;
    if ((output.width as number) * (output.height as number) > MAX_EXPORT_PIXELS) {
      errors.push('output: resolução acima de 4K (máx. 3840×2160 pixels).');
    }
  }

  // Extensões opcionais (retrocompatíveis): gerador + Satisfying Objects.
  let generator: GeneratorId | undefined;
  if (raw.generator !== undefined) {
    if (GENERATOR_IDS.includes(raw.generator as GeneratorId))
      generator = raw.generator as GeneratorId;
    else
      errors.push(
        `generator: valor ${describe(raw.generator)} inválido. Opções: ${GENERATOR_IDS.join(', ')}.`,
      );
  }
  let satisfying: SatisfyingSettings | undefined;
  if (raw.satisfying !== undefined) {
    const result = validateSatisfyingSettings(raw.satisfying);
    if (result.ok) {
      satisfying = result.settings;
      warnings.push(...result.warnings);
    } else {
      errors.push(...result.errors);
    }
  } else if (generator === 'satisfying') {
    satisfying = createDefaultSatisfyingSettings();
    warnings.push('satisfying: ausente, usando valores padrão.');
  }

  if (errors.length > 0) return { ok: false, errors };

  const preset = {
    version: PRESET_VERSION,
    name: (raw.name as string).trim(),
    seed: normalizeSeed(raw.seed as number),
    timestamp: typeof raw.timestamp === 'number' ? raw.timestamp : 0,
    ...(typeof raw.description === 'string' ? { description: raw.description } : {}),
    ...(generator !== undefined ? { generator } : {}),
    ...sections,
    path,
    ...(satisfying !== undefined ? { satisfying } : {}),
  } as unknown as ScenePreset;
  return { ok: true, preset, warnings, migratedFrom: migrated.migratedFrom };
}

export function serializePreset(preset: ScenePreset): string {
  return JSON.stringify(preset, null, 2);
}

export function deserializePreset(json: string): PresetValidationResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(json);
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { ok: false, errors: [`JSON inválido: ${reason}`] };
  }
  return validatePreset(parsed);
}
