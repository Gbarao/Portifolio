import { normalizeSeed } from '../core/SeededRandom';
import { validatePathPoints } from '../path/PathValidator';
import { createDefaultProject } from './DefaultPresets';
import {
  MAX_EXPORT_PIXELS,
  MAX_PATH_POINTS,
  MIN_PATH_POINTS,
  PATH_SPECS,
  POINT_COORD_LIMIT,
  PRESET_VERSION,
  SECTION_SPECS,
  type FieldSpec,
  type ScenePreset,
  type Vec3Like,
} from './PresetSchema';

export type PresetValidationResult =
  | { ok: true; preset: ScenePreset; warnings: string[]; migratedFrom: number | null }
  | { ok: false; errors: string[] };

type RawObject = Record<string, unknown>;

function isObject(value: unknown): value is RawObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function describe(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'lista';
  if (typeof value === 'string') return `"${value.length > 24 ? `${value.slice(0, 24)}…` : value}"`;
  return String(value);
}

function parseColor(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 0xffffff) {
    return value;
  }
  if (typeof value === 'string' && /^#?[0-9a-fA-F]{6}$/.test(value)) {
    return parseInt(value.replace('#', ''), 16);
  }
  return null;
}

function checkField(spec: FieldSpec, value: unknown, path: string, errors: string[]): unknown {
  switch (spec.kind) {
    case 'number': {
      if (typeof value !== 'number' || !Number.isFinite(value)) {
        errors.push(`${path}: esperado número, recebido ${describe(value)}.`);
        return undefined;
      }
      if (spec.integer && !Number.isInteger(value)) {
        errors.push(`${path}: esperado número inteiro, recebido ${value}.`);
        return undefined;
      }
      if (value < spec.min || value > spec.max) {
        errors.push(`${path}: valor ${value} fora do intervalo [${spec.min}, ${spec.max}].`);
        return undefined;
      }
      return value;
    }
    case 'boolean':
      if (typeof value !== 'boolean') {
        errors.push(`${path}: esperado true/false, recebido ${describe(value)}.`);
        return undefined;
      }
      return value;
    case 'enum':
      if (!spec.values.includes(value as string | number)) {
        errors.push(
          `${path}: valor ${describe(value)} inválido. Opções: ${spec.values.join(', ')}.`,
        );
        return undefined;
      }
      return value;
    case 'color': {
      const color = parseColor(value);
      if (color === null) {
        errors.push(
          `${path}: cor inválida ${describe(value)} (use inteiro 0–0xFFFFFF ou "#RRGGBB").`,
        );
        return undefined;
      }
      return color;
    }
    case 'vec3': {
      if (!isObject(value)) {
        errors.push(`${path}: esperado objeto {x, y, z}.`);
        return undefined;
      }
      const result: Vec3Like = { x: 0, y: 0, z: 0 };
      for (const axis of ['x', 'y', 'z'] as const) {
        const v = value[axis];
        if (typeof v !== 'number' || !Number.isFinite(v) || v < spec.min || v > spec.max) {
          errors.push(
            `${path}.${axis}: esperado número em [${spec.min}, ${spec.max}], recebido ${describe(v)}.`,
          );
          return undefined;
        }
        result[axis] = v;
      }
      return result;
    }
    case 'string':
      if (typeof value !== 'string' || value.length > spec.maxLength) {
        errors.push(`${path}: esperado texto com até ${spec.maxLength} caracteres.`);
        return undefined;
      }
      return value;
    case 'colorList': {
      if (!Array.isArray(value) || value.length < spec.minLength || value.length > spec.maxLength) {
        errors.push(`${path}: esperado lista com ${spec.minLength}–${spec.maxLength} cores.`);
        return undefined;
      }
      const colors: number[] = [];
      for (const [i, item] of value.entries()) {
        const color = parseColor(item);
        if (color === null) {
          errors.push(`${path}[${i}]: cor inválida ${describe(item)}.`);
          return undefined;
        }
        colors.push(color);
      }
      return colors;
    }
  }
}

function validateSection(
  raw: unknown,
  specs: Record<string, FieldSpec>,
  defaults: RawObject,
  sectionName: string,
  errors: string[],
  warnings: string[],
): RawObject {
  const result: RawObject = {};
  if (!isObject(raw)) {
    errors.push(`${sectionName}: seção ausente ou inválida.`);
    return result;
  }
  for (const [key, spec] of Object.entries(specs)) {
    const path = `${sectionName}.${key}`;
    if (raw[key] === undefined) {
      if (spec.required) {
        errors.push(`${path}: campo obrigatório ausente.`);
      } else {
        result[key] = structuredClone(defaults[key]);
        warnings.push(`${path}: ausente, usando valor padrão.`);
      }
      continue;
    }
    const checked = checkField(spec, raw[key], path, errors);
    if (checked !== undefined) result[key] = checked;
  }
  return result;
}

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

  if (errors.length > 0) return { ok: false, errors };

  const preset = {
    version: PRESET_VERSION,
    name: (raw.name as string).trim(),
    seed: normalizeSeed(raw.seed as number),
    timestamp: typeof raw.timestamp === 'number' ? raw.timestamp : 0,
    ...(typeof raw.description === 'string' ? { description: raw.description } : {}),
    ...sections,
    path,
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
