import { describe, expect, it } from 'vitest';
import { ExportHistory, type ExportHistoryEntry } from '../export/ExportHistory';
import {
  estimateFileSizeBytes,
  resolveExportPlan,
  validateExport,
} from '../export/ExportValidator';
import { buildExportFileName, slugify } from '../export/FileNaming';
import { ZipWriter, crc32 } from '../export/ZipWriter';
import { createDefaultProject } from '../presets/DefaultPresets';
import { MemoryStorage } from '../presets/PresetStore';

const runtimeOk = { helpersHidden: true, guiHidden: true, mediaRecorderSupported: true };

describe('Validação pré-export', () => {
  it('projeto padrão passa no checklist', () => {
    const result = validateExport(createDefaultProject(), 'video', runtimeOk);
    expect(result.errors).toEqual([]);
    expect(result.ok).toBe(true);
    expect(result.plan).toEqual({
      durationSeconds: 8,
      totalFrames: 240,
      framesPerLoop: 240,
      loopRepeats: 1,
    });
    const ids = result.checks.map((c) => c.id);
    for (const id of [
      'pathClosed',
      'marbleCycles',
      'cameraCycles',
      'duration',
      'resolution',
      'frameGrid',
      'frameLimit',
      'helpers',
      'gui',
    ]) {
      expect(ids).toContain(id);
    }
  });

  it('bloqueia curva aberta', () => {
    const project = createDefaultProject();
    project.path.closed = false;
    const result = validateExport(project, 'video', runtimeOk);
    expect(result.ok).toBe(false);
    expect(result.errors[0]).toContain('fechada');
  });

  it('bloqueia ciclos não inteiros (bolinhas e câmera animada)', () => {
    const project = createDefaultProject();
    project.marbles.cycleCount = 1.5;
    expect(validateExport(project, 'video', null).ok).toBe(false);
    const camera = createDefaultProject();
    camera.camera.mode = 'orbit';
    camera.camera.cycleCount = 0.5;
    expect(validateExport(camera, 'video', null).ok).toBe(false);
  });

  it('bloqueia resolução acima de 4K, ímpar ou com proporção extrema', () => {
    for (const [w, h] of [
      [3840, 3840],
      [1081, 1920],
      [4000, 1000],
      [100, 3000],
    ] as const) {
      const project = createDefaultProject();
      project.output.width = w;
      project.output.height = h;
      expect(validateExport(project, 'image', null).ok).toBe(false);
    }
    const ok = createDefaultProject();
    ok.output.width = 3840;
    ok.output.height = 2160;
    expect(validateExport(ok, 'image', null).ok).toBe(true);
  });

  it('bloqueia totalFrames não inteiro', () => {
    const project = createDefaultProject();
    project.loop.durationSeconds = 7.51;
    project.output.durationSeconds = 7.51;
    const result = validateExport(project, 'video', null);
    expect(result.ok).toBe(false);
    expect(result.checks.find((c) => c.id === 'frameGrid')?.ok).toBe(false);
  });

  it('exige helpers e GUI ocultos na captura', () => {
    const result = validateExport(createDefaultProject(), 'video', {
      ...runtimeOk,
      helpersHidden: false,
      guiHidden: false,
    });
    expect(result.ok).toBe(false);
    expect(result.errors).toHaveLength(2);
  });

  it('avisa (sem bloquear) sobre configuração pesada e ausência de MediaRecorder', () => {
    const project = createDefaultProject();
    project.marbles.count = 200;
    const result = validateExport(project, 'video', {
      ...runtimeOk,
      mediaRecorderSupported: false,
    });
    expect(result.ok).toBe(true);
    expect(result.warnings).toHaveLength(2);
  });

  it('autoLoop ajusta a duração para múltiplo inteiro do loop', () => {
    const project = createDefaultProject();
    project.output.durationSeconds = 19;
    expect(resolveExportPlan(project.output, project.loop)).toMatchObject({
      durationSeconds: 16,
      loopRepeats: 2,
      totalFrames: 480,
    });
    project.output.durationSeconds = 20;
    expect(resolveExportPlan(project.output, project.loop).durationSeconds).toBe(24);
    project.output.fps = 60;
    project.output.durationSeconds = 3;
    expect(resolveExportPlan(project.output, project.loop)).toMatchObject({
      durationSeconds: 8,
      totalFrames: 480,
    });
    project.output.autoLoop = false;
    project.output.durationSeconds = 12;
    const result = validateExport(project, 'video', null);
    expect(result.ok).toBe(true);
    expect(result.warnings.some((w) => w.includes('múltipla'))).toBe(true);
  });

  it('estima tamanho do arquivo pelo bitrate', () => {
    expect(estimateFileSizeBytes(5, 8)).toBe(5_000_000);
  });
});

describe('Nomes de arquivo', () => {
  it('segue infinite-marble-{preset}-{seed}-{w}x{h}.{ext}', () => {
    const project = createDefaultProject();
    project.name = 'Golden Spiral';
    project.seed = 42;
    expect(buildExportFileName(project, 'webm')).toBe(
      'infinite-marble-golden-spiral-42-1080x1920.webm',
    );
    expect(buildExportFileName(project, 'png')).toBe(
      'infinite-marble-golden-spiral-42-1080x1920.png',
    );
    project.output.fileName = 'Meu Vídeo Final.webm';
    expect(buildExportFileName(project, 'webm')).toBe('meu-video-final.webm');
  });

  it('slugify remove acentos e caracteres especiais', () => {
    expect(slugify('Órbita Ção! #1')).toBe('orbita-cao-1');
    expect(slugify('***')).toBe('projeto');
  });
});

describe('ZipWriter', () => {
  it('CRC-32 correto (vetor de teste "123456789")', () => {
    expect(crc32(new TextEncoder().encode('123456789'))).toBe(0xcbf43926);
  });

  it('gera ZIP STORE com cabeçalhos e diretório central válidos', async () => {
    const zip = new ZipWriter();
    zip.addText('a.txt', 'hello');
    zip.addFile('frames/frame_00000.png', new Uint8Array([1, 2, 3, 4]));
    const bytes = zip.finishBytes();
    const view = new DataView(bytes.buffer);
    expect(view.getUint32(0, true)).toBe(0x04034b50);
    const eocd = bytes.length - 22;
    expect(view.getUint32(eocd, true)).toBe(0x06054b50);
    expect(view.getUint16(eocd + 10, true)).toBe(2);
    const cdOffset = view.getUint32(eocd + 16, true);
    expect(view.getUint32(cdOffset, true)).toBe(0x02014b50);
    expect(zip.fileCount).toBe(2);
    const blob = zip.finish();
    expect(blob.size).toBe(bytes.length);
    expect(new Uint8Array(await blob.arrayBuffer())).toEqual(bytes);
  });
});

describe('Histórico de exportações', () => {
  const entry = (id: string, createdAt: number): ExportHistoryEntry => ({
    id,
    kind: 'video',
    fileName: `${id}.webm`,
    width: 1080,
    height: 1920,
    fps: 30,
    durationSeconds: 8,
    createdAt,
    seed: 1,
    presetName: 'Teste',
    thumbnail: '',
    snapshot: '{}',
    normalizedTime: 0,
  });

  it('mantém apenas as 10 últimas exportações, mais recentes primeiro', () => {
    const history = new ExportHistory(new MemoryStorage());
    for (let i = 0; i < 14; i++) history.add(entry(`e${i}`, i));
    const list = history.list();
    expect(list).toHaveLength(10);
    expect(list[0]!.id).toBe('e13');
    expect(history.remove('e13')).toHaveLength(9);
    history.clear();
    expect(history.list()).toEqual([]);
    expect(history.createId(1000)).not.toBe(history.createId(1000));
  });
});
