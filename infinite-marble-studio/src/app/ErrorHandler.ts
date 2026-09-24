export type NotifyLevel = 'info' | 'success' | 'warning' | 'error';

export interface NotifyAction {
  label: string;
  run: () => void;
}

export type NotifyFn = (message: string, level: NotifyLevel, action?: NotifyAction) => void;

/** Tratamento centralizado de erros: mensagens compreensíveis na interface + console. */
export class ErrorHandler {
  constructor(private readonly notify: NotifyFn) {}

  static describe(error: unknown): string {
    if (error instanceof Error) return error.message || error.name;
    if (typeof error === 'string') return error;
    try {
      return JSON.stringify(error);
    } catch {
      return String(error);
    }
  }

  install(): void {
    window.addEventListener('error', (event) => {
      this.report(event.error ?? event.message, 'Erro inesperado');
    });
    window.addEventListener('unhandledrejection', (event) => {
      this.report(event.reason, 'Operação falhou');
    });
  }

  report(error: unknown, context?: string, action?: NotifyAction): void {
    const message = ErrorHandler.describe(error);
    console.error(context ? `${context}:` : 'Erro:', error);
    this.notify(context ? `${context}: ${message}` : message, 'error', action);
  }
}
