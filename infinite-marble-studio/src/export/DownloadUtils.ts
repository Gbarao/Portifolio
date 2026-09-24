/** Baixa um Blob via <a download> e revoga a URL em seguida. */
export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  anchor.rel = 'noopener';
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revogação adiada: alguns navegadores cancelam o download se a URL some imediatamente.
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export function downloadText(text: string, fileName: string, type = 'application/json'): void {
  downloadBlob(new Blob([text], { type }), fileName);
}

/**
 * Lê o conteúdo do canvas como Blob. Deve ser chamado na mesma tarefa da renderização
 * (preserveDrawingBuffer = false).
 */
export function canvasToBlob(
  canvas: HTMLCanvasElement,
  type = 'image/png',
  quality?: number,
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Falha ao gerar a imagem do canvas.'))),
      type,
      quality,
    );
  });
}

/** Miniatura JPEG pequena (para o histórico em localStorage). */
export function createThumbnail(source: HTMLCanvasElement, maxSize = 160): string {
  const scale = maxSize / Math.max(source.width, source.height);
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(source.width * scale));
  canvas.height = Math.max(1, Math.round(source.height * scale));
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.7);
}
