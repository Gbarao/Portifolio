type Attributes = Record<string, string | number | boolean | undefined>;

/** Cria um elemento com atributos e filhos (texto ou nós). */
export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attributes: Attributes = {},
  children: (Node | string)[] = [],
): HTMLElementTagNameMap[K] {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === undefined || value === false) continue;
    if (name === 'className') element.className = String(value);
    else if (name === 'text') element.textContent = String(value);
    else element.setAttribute(name, value === true ? '' : String(value));
  }
  for (const child of children) {
    element.append(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return element;
}

export function button(
  label: string,
  title: string,
  onClick: () => void,
  className = 'btn',
): HTMLButtonElement {
  const b = el('button', { type: 'button', className, title, 'aria-label': title }, [label]);
  b.addEventListener('click', onClick);
  return b;
}

export function requireElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Elemento #${id} não encontrado no HTML.`);
  return element as T;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}
