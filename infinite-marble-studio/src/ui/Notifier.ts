import type { NotifyAction, NotifyLevel } from '../app/ErrorHandler';
import { button, el } from './dom';

const DEFAULT_TIMEOUT: Record<NotifyLevel, number> = {
  info: 3500,
  success: 3000,
  warning: 6000,
  error: 9000,
};

/** Mensagens temporárias (toasts) acessíveis via aria-live. */
export class Notifier {
  constructor(private readonly container: HTMLElement) {}

  show(
    message: string,
    level: NotifyLevel = 'info',
    action?: NotifyAction,
    timeoutMs?: number,
  ): void {
    const text = el('div', { className: 'toast-text' });
    text.textContent = message;
    const toast = el(
      'div',
      { className: `toast toast-${level}`, role: level === 'error' ? 'alert' : 'status' },
      [text],
    );
    const close = (): void => toast.remove();
    if (action) {
      toast.append(
        button(
          action.label,
          action.label,
          () => {
            action.run();
            close();
          },
          'btn btn-small',
        ),
      );
    }
    toast.append(button('×', 'Fechar mensagem', close, 'btn btn-icon toast-close'));
    this.container.append(toast);
    while (this.container.children.length > 5) this.container.firstElementChild?.remove();
    setTimeout(close, timeoutMs ?? DEFAULT_TIMEOUT[level] + (action ? 6000 : 0));
  }
}
