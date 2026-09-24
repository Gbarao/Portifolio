import type { VideoExportProgress } from '../export/VideoExporter';
import { button, el, formatDuration } from './dom';

export interface ExportProgressActions {
  cancel(): void;
  rerecord(): void;
}

/** Sobreposição de progresso da exportação: barra, percentual, tempos, cancelar, re-gravar. */
export class ExportProgress {
  private readonly title = el('h2', { id: 'export-title' });
  private readonly bar = el('progress', {
    max: '100',
    value: '0',
    'aria-labelledby': 'export-title',
  });
  private readonly percent = el('div', { className: 'export-percent' });
  private readonly detail = el('div', { className: 'export-detail' });
  private readonly message = el('div', { className: 'export-message' });
  private readonly cancelButton: HTMLButtonElement;
  private readonly rerecordButton: HTMLButtonElement;
  private readonly closeButton: HTMLButtonElement;
  /** Espelho compacto dentro do painel "Exportação". */
  readonly inline = el('div', { className: 'inline-progress' });
  private readonly inlineBar = el('progress', { max: '100', value: '0' });
  private readonly inlineText = el('span', { className: 'inline-progress-text' }, ['Pronto']);

  constructor(
    private readonly overlay: HTMLElement,
    actions: ExportProgressActions,
  ) {
    this.cancelButton = button(
      'Cancelar',
      'Cancelar a exportação',
      actions.cancel,
      'btn btn-danger',
    );
    this.rerecordButton = button(
      'Re-gravar',
      'Gravar novamente com as mesmas configurações',
      actions.rerecord,
      'btn',
    );
    this.closeButton = button('Fechar', 'Fechar', () => this.hide(), 'btn btn-primary');
    const panel = el(
      'div',
      {
        className: 'export-panel',
        role: 'dialog',
        'aria-modal': 'true',
        'aria-labelledby': 'export-title',
      },
      [
        this.title,
        this.bar,
        this.percent,
        this.detail,
        this.message,
        el('div', { className: 'export-actions' }, [
          this.cancelButton,
          this.rerecordButton,
          this.closeButton,
        ]),
      ],
    );
    overlay.append(panel);
    this.inline.append(this.inlineBar, this.inlineText);
  }

  start(title: string, detail: string, mode: 'realtime' | 'offline' = 'realtime'): void {
    this.overlay.hidden = false;
    this.title.textContent = title;
    this.bar.value = 0;
    this.percent.textContent = '0%';
    this.detail.textContent = detail;
    this.message.textContent =
      mode === 'realtime'
        ? 'Gravação em tempo real: mantenha esta aba visível (a gravação pausa se a aba ficar oculta).'
        : 'Codificação frame a frame (WebCodecs): timestamps exatos, independente da velocidade da GPU.';
    this.message.dataset.level = 'info';
    this.cancelButton.hidden = false;
    this.rerecordButton.hidden = true;
    this.closeButton.hidden = true;
    this.inlineBar.value = 0;
    this.inlineText.textContent = 'Gravando… 0%';
  }

  update(progress: VideoExportProgress): void {
    const pct = Math.min(100, progress.percent);
    this.bar.value = pct;
    this.percent.textContent = `${pct.toFixed(1)}%`;
    this.detail.textContent = `Frame ${progress.frame}/${progress.totalFrames} · decorrido ${formatDuration(
      progress.elapsedMs,
    )} / estimado ${formatDuration(progress.estimatedTotalMs)}`;
    if (progress.lagMs > 100) {
      this.message.textContent = `Renderização mais lenta que o tempo real (atraso ${Math.round(progress.lagMs)} ms): o timing do vídeo pode variar. O encoder WebCodecs evita isso.`;
      this.message.dataset.level = 'warning';
    }
    this.inlineBar.value = pct;
    this.inlineText.textContent = `Gravando… ${pct.toFixed(0)}%`;
  }

  finish(message: string, level: 'success' | 'warning' | 'error', allowRerecord: boolean): void {
    this.message.textContent = message;
    this.message.dataset.level = level;
    this.cancelButton.hidden = true;
    this.rerecordButton.hidden = !allowRerecord;
    this.closeButton.hidden = false;
    this.inlineText.textContent = level === 'success' ? 'Concluído' : message;
    if (level === 'success') {
      this.bar.value = 100;
      this.percent.textContent = '100%';
      this.inlineBar.value = 100;
    }
    this.closeButton.focus();
  }

  showErrors(title: string, errors: readonly string[]): void {
    this.overlay.hidden = false;
    this.title.textContent = title;
    this.bar.value = 0;
    this.percent.textContent = '';
    this.detail.textContent = '';
    this.finish(errors.map((e) => `• ${e}`).join('\n'), 'error', false);
    this.inlineText.textContent = 'Validação falhou';
  }

  hide(): void {
    this.overlay.hidden = true;
  }
}
