# Roadmap

A versão 1 (MVP) está completa. Os itens abaixo **não fazem parte da v1** e ficam registrados aqui
para evitar aumento de escopo.

## Já implementado após a v1

- Trilho **Groove** (canaleta em U), acabamento madeira, hastes de suporte, verniz, sombras suaves
  e cúpulas decorativas.
- Modo simples e arquivo único que abre com dois cliques.
- **Satisfying Objects · Squeeze** (subsistema `src/satisfying/`): Soft Block + esfera, 9
  materiais, 8 iluminações, 6 presets, variação, lote de configurações.

## Satisfying Objects — próximos passos (não implementado)

- Ações Crush, Stretch, Push, Pinch e Roll (a arquitetura `PressureTool` já prevê).
- Ferramentas Plate, Cylinder, Roller, Wedge, dedo procedural e multiponto.
- Outras formas (esfera macia, cilindro, "mochi").
- Renderização em lote de vídeos (hoje o lote gera as configurações JSON).
- Deformação no vertex shader caso a CPU limite o preview em GPUs reais (função já é pura).

## Fase 2 (não implementado)

- Modo infinito (geração procedural contínua).
- Chunking e object pooling para cenas enormes.
- Publicação automática em TikTok/Instagram.
- Streaming ao vivo.
- Multiplayer ou sincronização.
- Modo de física (rigid body dynamics).
- Texturas e modelos importados.
- Sincronia com áudio e beat mapping.
- Editor de shader customizado.
- Sistema de plug-ins.

## Melhorias candidatas (pós-v1)

- Exportação MP4 (H.264) direta via WebCodecs + muxer MP4, sem FFmpeg.
- Presets de câmera com trajetórias próprias (curvas de câmera editáveis).
- Mais paletas e gradientes de cor por bolinha ao longo da curva.
- Teste end-to-end automatizado em navegador (Playwright) para exportação e pixels.
