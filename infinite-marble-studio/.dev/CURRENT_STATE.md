# Current State

Current Phase:
Phase 1 — Visual Prototype — CONCLUÍDA (validação visual PASS).
Próxima: Phase 2–4 (engine/materiais/tool) já têm base; Phase 5 editor + integração.

Completed:

- Fase 0: discovery (.dev/DISCOVERY.md), decisões (.dev/DECISIONS.md, Estratégia B).
- src/satisfying/ (subsistema isolado; Marble Studio não foi modificado):
  - geometry/SoftBlockGeometry.ts — rounded box soldada, alta subdivisão.
  - animation/PressureCurve.ts — fases (repouso→aproximação→contato→pico→hold→
    soltura→recuperação viscosa + rebote elástico→repouso), periódica.
  - deformation/SqueezeDeformer.ts — compressão global + Hertz local + conformação
    à esfera + bulging + compensação de volume na malha (2 passadas) + contato +
    oclusão por vértice. deformation/MeshNormals.ts — normais/volume/áreas.
  - pressure/PressureTool.ts (interface) + SpherePressureTool.ts.
  - materials/SatisfyingMaterials.ts — 9 tipos (softRubber, glossyGel, slime, foam,
    silicone, wax, softPlastic, butter, candy).
  - lighting/SatisfyingLighting.ts — key (VSM suave) + fill + rim + top (RectArea)
    - hemisfério + RoomEnvironment; 8 presets.
  - camera/MacroCameraRig.ts — macro vertical, órbita/dolly periódicos.
  - scene/StudioBackdrop.ts (ciclorama), scene/ContactShadow.ts (sombra analítica).
  - SatisfyingSettings.ts (tipos + defaults), SqueezeSimulation.ts (sem WebGL),
    SqueezeScene.ts (cena WebGL).
  - lab/squeezeLab.ts + lab/squeeze.html (apenas dev).
- src/tests/Squeeze.test.ts (17 testes).

Arquivos modificados fora de src/satisfying: nenhum (apenas novos testes/lab/.dev).

Estado do build: PASS. Estado visual: PASS (ver VALIDATION.md).

Known limitations:

- Só squeeze + esfera + soft block (por decisão do MVP).
- Ainda sem UI no app principal, sem persistência, sem export integrado.
- Lighting usa VSMShadowMap: ao integrar no App, restaurar PCFShadowMap ao voltar
  para o Marble Run (ver DECISIONS D-007).

Next Exact Step:
Integração no App (Phase 5): seletor de gerador "Marble Run | Satisfying Objects"

- painel do Squeeze + delegação de render/captura (CaptureHost) — ver TODO_NEXT.md.
