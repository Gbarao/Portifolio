# Roadmap

A versão 1 (MVP) está completa. Os itens abaixo **não fazem parte da v1** e ficam registrados aqui
para evitar aumento de escopo.

## Fase 2 (não implementado)

- Trilho **Groove**: canal côncavo/pista em U (ponto de extensão em `src/track/TrackBuilder.ts`,
  marcado com `// TODO FUTURE: Groove track builder`).
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
