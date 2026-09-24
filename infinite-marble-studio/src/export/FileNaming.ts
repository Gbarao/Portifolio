import type { ScenePreset } from '../presets/PresetSchema';

export type ExportExtension = 'png' | 'webm' | 'zip' | 'json';

/** Converte texto em slug seguro para nomes de arquivo. */
export function slugify(text: string, fallback = 'projeto'): string {
  const slug = text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .replace(/-+$/g, '');
  return slug || fallback;
}

/** infinite-marble-{preset}-{seed}-{width}x{height}.{ext} (ou o nome customizado). */
export function buildExportFileName(
  project: Pick<ScenePreset, 'name' | 'seed' | 'output'>,
  extension: ExportExtension,
): string {
  const custom = project.output.fileName.trim();
  if (custom) return `${slugify(custom.replace(/\.(png|webm|zip|json)$/i, ''))}.${extension}`;
  const { width, height } = project.output;
  return `infinite-marble-${slugify(project.name)}-${project.seed}-${width}x${height}.${extension}`;
}
