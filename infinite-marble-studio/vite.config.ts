import { defineConfig, type Plugin } from 'vite';

const SINGLE_FILE_NAME = 'InfiniteMarbleStudio.html';

const escapeRegExp = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Embute JS e CSS no HTML: o resultado é um único arquivo que funciona ao ser aberto
 * direto do disco (file://), sem servidor e sem instalação.
 */
function singleFile(): Plugin {
  return {
    name: 'ims-single-file',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const page = bundle['index.html'];
      if (!page || page.type !== 'asset') return;
      let html = String(page.source);
      for (const [fileName, output] of Object.entries(bundle)) {
        if (output.type === 'chunk') {
          const code = output.code.replace(/<\/script/gi, '<\\/script');
          const tag = new RegExp(`<script[^>]*src="[^"]*${escapeRegExp(fileName)}"[^>]*></script>`);
          // Função de substituição: evita que "$&", "$'" etc. do código sejam interpretados.
          html = html.replace(tag, () => `<script type="module">${code}</script>`);
          delete bundle[fileName];
        } else if (fileName.endsWith('.css')) {
          const tag = new RegExp(`<link[^>]*href="[^"]*${escapeRegExp(fileName)}"[^>]*>`);
          html = html.replace(tag, () => `<style>${String(output.source)}</style>`);
          delete bundle[fileName];
        }
      }
      delete bundle['index.html'];
      this.emitFile({ type: 'asset', fileName: SINGLE_FILE_NAME, source: html });
    },
  };
}

export default defineConfig(({ mode }) => {
  const single = mode === 'single';
  return {
    // Caminhos relativos: o build funciona aberto de qualquer subpasta.
    base: './',
    plugins: single ? [singleFile()] : [],
    server: {
      port: 5173,
      host: 'localhost',
    },
    preview: {
      port: 4173,
    },
    build: {
      target: 'es2022',
      outDir: single ? 'release' : 'dist',
      sourcemap: !single,
      cssCodeSplit: !single,
      // three.js sozinho ocupa ~700 KB minificado.
      chunkSizeWarningLimit: 1200,
    },
  };
});
