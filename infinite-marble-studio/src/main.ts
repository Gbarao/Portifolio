import './styles/main.css';
import './styles/ui.css';
import './styles/responsive.css';
import { App } from './app/App';

declare global {
  interface Window {
    /** Acesso para depuração pelo console do navegador. */
    infiniteMarbleStudio?: App;
  }
}

function showFatalError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  const root = document.getElementById('app') ?? document.body;
  const box = document.createElement('div');
  box.className = 'fatal-error';
  box.setAttribute('role', 'alert');
  const title = document.createElement('h1');
  title.textContent = 'Não foi possível iniciar o Infinite Marble Studio';
  const detail = document.createElement('p');
  detail.textContent = message;
  const hint = document.createElement('p');
  hint.textContent =
    'Verifique se o navegador suporta WebGL 2 (Chrome, Edge ou Firefox atualizados) e se a aceleração de hardware está ativada.';
  box.append(title, detail, hint);
  root.replaceChildren(box);
  console.error(error);
}

try {
  const app = new App();
  app.start();
  window.infiniteMarbleStudio = app;
} catch (error) {
  showFatalError(error);
}
