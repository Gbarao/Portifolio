import type { PerformanceSnapshot } from '../core/PerformanceMonitor';
import { el, formatBytes, formatDuration } from './dom';

export interface StatusData {
  performance: PerformanceSnapshot;
  drawCalls: number;
  triangles: number;
  memoryBytes: number;
  curveClosed: boolean;
  curveValid: boolean;
  seed: number;
  marbleCount: number;
  loopSeconds: number;
  estimatedFileBytes: number;
  exportSeconds: number;
  recordingElapsedMs: number | null;
  recommendations: string[];
  /** Presente quando o gerador Satisfying Objects está ativo. */
  satisfying?: { vertices: number; deformMs: number };
}

/** Painel de desempenho e status em tempo real (sobre a cena, oculto nas capturas). */
export class StatusPanel {
  private readonly fps = el('span', { className: 'stat-value' });
  private readonly minMax = el('span', { className: 'stat-value' });
  private readonly calls = el('span', { className: 'stat-value' });
  private readonly memory = el('span', { className: 'stat-value' });
  private readonly curve = el('span', { className: 'stat-value' });
  private readonly project = el('span', { className: 'stat-value' });
  private readonly file = el('span', { className: 'stat-value' });
  private readonly recording = el('span', { className: 'stat-value' });
  private readonly recordingRow: HTMLElement;
  private readonly tips = el('ul', { className: 'stat-tips' });
  private readonly curveLabel = el('span', { className: 'stat-label' }, ['Curva']);

  constructor(private readonly container: HTMLElement) {
    const row = (label: string, value: HTMLElement, title: string): HTMLElement =>
      el('div', { className: 'stat-row', title }, [
        el('span', { className: 'stat-label' }, [label]),
        value,
      ]);
    this.recordingRow = row('Gravação', this.recording, 'Tempo decorrido da gravação');
    this.recordingRow.hidden = true;
    container.append(
      row('FPS', this.fps, 'Média dos últimos 60 frames'),
      row('Mín/Máx', this.minMax, 'FPS mínimo e máximo nos últimos 60 frames'),
      row('Draw calls', this.calls, 'WebGLRenderer.info.render.calls'),
      row('Memória', this.memory, 'Estimativa aproximada: geometrias, texturas e sombras'),
      el('div', { className: 'stat-row', title: 'Curva (Marble Run) ou malha (Squeeze)' }, [
        this.curveLabel,
        this.curve,
      ]),
      row('Projeto', this.project, 'Seed, bolinhas e duração do loop'),
      row('Arquivo', this.file, 'Tamanho estimado do vídeo (bitrate × duração)'),
      this.recordingRow,
      this.tips,
    );
  }

  setVisible(visible: boolean): void {
    this.container.hidden = !visible;
  }

  update(data: StatusData): void {
    const p = data.performance;
    this.fps.textContent = p.sampleCount > 0 ? p.fps.toFixed(0) : '–';
    this.fps.dataset.level = p.level;
    this.minMax.textContent =
      p.sampleCount > 0 ? `${p.minFps.toFixed(0)} / ${p.maxFps.toFixed(0)}` : '–';
    this.calls.textContent = `${data.drawCalls} (${(data.triangles / 1000).toFixed(0)}k tri)`;
    this.memory.textContent = `~${formatBytes(data.memoryBytes)}`;
    if (data.satisfying) {
      const sq = data.satisfying;
      this.curveLabel.textContent = 'Malha';
      this.curve.textContent = `${(sq.vertices / 1000).toFixed(1)}k vért. · ${sq.deformMs.toFixed(1)} ms`;
      this.curve.dataset.level =
        sq.deformMs < 8 ? 'good' : sq.deformMs < 16 ? 'warning' : 'critical';
      this.project.textContent = `seed ${data.seed} · squeeze · ${data.loopSeconds}s`;
    } else {
      this.curveLabel.textContent = 'Curva';
      this.curve.textContent = `${data.curveClosed ? 'fechada' : 'aberta'} · ${data.curveValid ? 'válida' : 'inválida'}`;
      this.curve.dataset.level = data.curveClosed && data.curveValid ? 'good' : 'critical';
      this.project.textContent = `seed ${data.seed} · ${data.marbleCount} bolinhas · ${data.loopSeconds}s`;
    }
    this.file.textContent = `~${formatBytes(data.estimatedFileBytes)} (${data.exportSeconds}s)`;
    this.recordingRow.hidden = data.recordingElapsedMs === null;
    if (data.recordingElapsedMs !== null) {
      this.recording.textContent = formatDuration(data.recordingElapsedMs);
    }
    this.tips.replaceChildren(...data.recommendations.map((tip) => el('li', {}, [tip])));
  }
}
