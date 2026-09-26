# Current State

Current Phase:
MVP do Squeeze concluído (Fases 0–9). Fase atual: refinamento/manutenção.

Completed:

- Fase 0: discovery (.dev/DISCOVERY.md) e decisões (.dev/DECISIONS.md, Estratégia B).
- Fase 1: protótipo visual validado (Soft Block + esfera, contato, bulging, volume).
- Fase 2: engine de deformação reutilizável (SqueezeDeformer puro + SqueezeSimulation).
- Fase 3: 9 materiais procedurais (SatisfyingMaterials.ts).
- Fase 4: PressureTool (interface) + SpherePressureTool.
- Fase 5: editor — SatisfyingPanel (lil-gui), seletor de gerador na TopBar, estilos e ações
  no modo simples, status adaptado.
- Fase 6: presets Pink Slime, Yellow Soft Block, Blue Gel, Candy Cube, Dark Rubber, Soft
  Silicone (validados visualmente: docs/satisfying-presets.png).
- Fase 7: Nova Variação (≥ 3 categorias, relatório VARIATION #seed).
- Fase 8: exportação integrada (PNG, WebM MediaRecorder/WebCodecs, formatos, duração, FPS,
  histórico) via App.renderFrame → mesmo caminho do Marble.
- Fase 9: lote (seed inicial + quantidade → ZIP de squeeze-<seed>.json).
- Persistência: ScenePreset v1 + `generator?` + `satisfying?` (retrocompatível).
- Docs: README (seção Satisfying Objects), ARCHITECTURE, ROADMAP.

Arquivos do Marble Studio modificados (aditivos):

- src/app/App.ts (delegação por gerador, painéis, variação/lote do squeeze)
- src/presets/PresetSchema.ts (campos opcionais), PresetValidator.ts (validação opcional),
  FieldValidation.ts (extraído, sem mudança de comportamento)
- src/scene/SceneManager.ts (setInteractive)
- src/ui/TopBar.ts, SimplePanel.ts, StatusPanel.ts, styles/ui.css
- vitest.config.ts (cobertura inclui src/satisfying)

Estado do build: PASS (build e build:single). Estado visual: PASS.

Known limitations:

- Performance em GPU real NÃO medida (ambiente só tem SwiftShader). Deformação: ~6 ms/frame
  em CPU no Chromium headless para ~30 mil vértices.
- Bundle 1,11 MB (RectAreaLight inclui tabelas LTC) — D-010.
- Lote gera configurações, não vídeos.
- Apenas Squeeze + esfera + bloco (escopo do MVP).

Next Exact Step:
Nenhuma pendência obrigatória. Candidatos em TODO_NEXT.md.
