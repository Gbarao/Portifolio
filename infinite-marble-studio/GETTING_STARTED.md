# Guia passo a passo

Este guia leva do zero até um vídeo vertical em loop perfeito.

## 1. Instalar e abrir

```bash
cd infinite-marble-studio
npm install
npm run dev
```

Abra `http://localhost:5173`. A cena padrão (onda 3D com 24 bolinhas) começa a tocar.

## 2. Conhecer a tela

- **Barra superior**: play/pause, reiniciar, randomizações, desfazer/refazer, helpers, vista livre,
  painel e ajuda (`?`).
- **Centro**: o canvas já na proporção da saída (9:16 por padrão). Canto inferior esquerdo:
  FPS, draw calls, memória, estado da curva e tamanho estimado do vídeo.
- **Painel à direita** (lil-gui), em 10 seções: Projeto, Trajeto, Trilho, Bolinhas, Câmera,
  Iluminação, Fundo, Loop, Exportação e Presets. `G` recolhe o painel.

## 3. Criar o trajeto

1. Em _2. Trajeto → Preset_, escolha **Torus knot (3,2)**.
2. Clique em uma das esferas azuis na cena. A linha correspondente da tabela é destacada.
3. Arraste uma seta do gizmo para mover o ponto. O trilho e as bolinhas acompanham a mudança.
4. Digite um valor em **Y** na tabela para edição precisa.
5. `Ctrl+Z` desfaz e `Ctrl+Shift+Z` refaz.
6. Se o trajeto ficar deslocado, clique em **AutoFitPath** (centraliza e ajusta ao raio 5).

O status abaixo dos botões precisa mostrar **✓ Curva fechada e válida** para exportar.

## 4. Ajustar a aparência

1. _3. Trilho_: estilo **Dual rail**, largura `0.5`, raio do trilho `0.06`.
2. _4. Bolinhas_: quantidade `48`, raio `0.2`, paleta **Neon**, velocidade `2` voltas.
3. _6. Iluminação → Preset_: **Dark Neon**.
4. _7. Fundo_: gradiente radial com cores escuras.

Dica: `Shift+A` sorteia só a aparência e `N` gera uma variação que altera 3 ou mais categorias,
com relatório das mudanças.

## 5. Enquadrar a câmera

1. _5. Câmera → Modo_: **Órbita** (1 ciclo por loop).
2. Mantenha **Enquadramento automático** ligado: a distância é calculada pela proporção da saída.
3. Ative _9. Exportação → Área segura_ para ver as margens de 20% onde o texto das plataformas
   costuma ficar.

## 6. Conferir o loop

1. _8. Loop_: duração `8 s`.
2. Pause (`Space`) e arraste **Tempo (0–1)** até perto de `0.999`, depois volte a `0`. As posições
   devem coincidir.
3. Em _9. Exportação_, clique em **Verificar determinismo**. O resultado esperado é
   `✓ Determinismo verificado … diferença máx. 0 … tolerância 2`.

## 7. Exportar

1. _9. Exportação → Resolução_: **Vertical 9:16 (1080×1920)**, FPS `30`, duração `8 s`.
2. Encoder: **MediaRecorder** (padrão) ou **WebCodecs**, que tem timestamps exatos e é indicado
   para máquinas mais lentas.
3. Clique em **Exportar vídeo** (`Ctrl+E`) e mantenha a aba visível.
4. O arquivo `infinite-marble-…-1080x1920.webm` é baixado ao final. Para MP4, veja o comando FFmpeg
   no README.
5. **Capturar PNG** gera a imagem do frame atual na mesma resolução.

## 8. Salvar o trabalho

- `Ctrl+S` salva o preset no navegador com o nome do projeto.
- _10. Presets → Exportar JSON_ baixa o arquivo para versionar ou compartilhar.
- Para abrir depois: _Importar JSON_ ou arraste o arquivo para a janela.
- O rascunho automático restaura o último estado ao reabrir a página.
