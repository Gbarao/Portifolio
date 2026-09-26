# Changelog — Satisfying Objects / Squeeze Engine

## Session 01

Added:

- `.dev/` (CURRENT_STATE, TODO_NEXT, CHANGELOG, DECISIONS, VALIDATION, DISCOVERY).
- Fase 0: discovery técnico/visual e decisão de arquitetura (Estratégia B).

Validated:

- Baseline do Marble Studio antes de qualquer alteração (ver VALIDATION.md).

Added (Fase 1):

- Subsistema `src/satisfying/` (geometria, curva de pressão, deformador, ferramenta
  esférica, materiais, iluminação, câmera macro, ciclorama, sombra de contato,
  simulação sem WebGL, cena WebGL).
- `lab/squeeze.html` (validação visual, só dev).
- `src/tests/Squeeze.test.ts` (17 testes).

Changed (iterações visuais):

- Enquadramento macro mais próximo; esfera cerâmica maior; força 0,42.
- Cavidade suaviza durante a recuperação (profileRadius cresce).
- Sombras VSM suaves; sombra de contato tingida; ciclorama sem estouro.
- Oclusão de contato por vértice.

Fixed:

- Erro de volume 3,5 % → 1,3 % (compensação medida na malha + estiramento).

Validated:

- Regressão completa (236 testes), build, runtime no navegador, capturas 0–100 %.

## Session 01 (continuação) — Fases 2–9

Added:

- SatisfyingSchema (validação FieldSpec), presets/FieldValidation (extraído do validador).
- ScenePreset: `generator?`, `satisfying?` (retrocompatível).
- SatisfyingController, SatisfyingPanel, seletor de gerador (TopBar), estilos/ações no modo
  simples, status com malha/tempo de deformação.
- 6 presets, Nova Variação (8 categorias), lote (ZIP de JSON).
- SqueezeScene.applySettings / SqueezeSimulation.updateSettings (sem reconstruir malha).
- SceneManager.setInteractive.
- Testes: src/tests/SqueezeIntegration.test.ts (16).
- Docs: README, ARCHITECTURE, ROADMAP; imagens em docs/.

Changed:

- Presets de luz candy/darkPremium: tone mapping neutral (AgX dessaturava cores).
- satinMetal mais rugoso; presets sem cromado (reflexos poluídos).

Validated:

- Regressão completa, build, build:single, e2e no navegador (dev e file://).
