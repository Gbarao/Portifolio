import type { FieldSpec, Vec3Like } from './PresetSchema';

/**
 * Validação genérica guiada por tabelas `FieldSpec` (compartilhada pelo schema do
 * Marble Run e pelo do Satisfying Objects).
 */

export type RawObject = Record<string, unknown>;

export function isObject(value: unknown): value is RawObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function describe(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'lista';
  if (typeof value === 'string') return `"${value.length > 24 ? `${value.slice(0, 24)}…` : value}"`;
  return String(value);
}

export function parseColor(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 0xffffff) {
    return value;
  }
  if (typeof value === 'string' && /^#?[0-9a-fA-F]{6}$/.test(value)) {
    return parseInt(value.replace('#', ''), 16);
  }
  return null;
}

export function checkField(
  spec: FieldSpec,
  value: unknown,
  path: string,
  errors: string[],
): unknown {
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

export function validateSection(
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
