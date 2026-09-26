# Discovery (Fase 0) — Infinite Marble Studio → Satisfying Objects

## Architecture Assessment

- Vite 8 + TypeScript 6 (strict) + three 0.186 + lil-gui 0.21; Vitest 5; ESLint 10 + Prettier.
- Entrada única `src/main.ts` → `App` (≈1340 linhas) orquestra estado (`AppState`),
  cena (`SceneManager`), UI (`ControlPanel` lil-gui, `SimplePanel`, `TopBar`), export.
- Tempo: `LoopClock` (preview por âncora de relógio com snap na grade de frames;
  export por `frameIndex`) → `normalizedTime` ∈ [0,1). Nada acumula delta time.
- Determinismo: Mulberry32 (`SeededRandom`), `deriveSeed(seed, salt)`, ESLint proíbe
  `Math.random`. `SeedSource` usa `crypto.getRandomValues` só para sortear seeds novas.
- Presets: `ScenePreset` v1 (output, loop, path, track, marbles, camera, lighting,
  background) validado por tabelas `FieldSpec`; migração v0→v1; `PresetStore` em
  localStorage; JSON import/export.
- Export: `VideoExporter` (MediaRecorder em tempo real; WebCodecs VP8/VP9 +
  `WebmMuxer` com timestamps exatos; PNG ZIP) via contrato `CaptureHost`.
- Build extra `build:single` gera `release/InfiniteMarbleStudio.html` (tudo embutido).

## Existing Renderer Assessment

- `RendererManager`: WebGLRenderer (antialias MSAA do contexto, PCFShadowMap),
  separa resolução de preview (CSS/devicePixelRatio) da de export (beginCapture).
- `LightingManager`: hemisphere + 3 direcionais + RoomEnvironment/PMREM, tone
  mapping configurável. Sem pós-processamento. Sem shaders customizados.
- Materiais: MeshPhysicalMaterial (clearcoat) em trilho e bolinhas.

## Reusable Systems (sem modificação)

LoopClock, SeededRandom/deriveSeed, PeriodicNoise, MathUtils, Disposable,
RendererManager, VideoExporter/WebmMuxer/ZipWriter/ImageExporter, FileNaming,
ExportValidator, CaptureHost, Notifier/ExportProgress (UI), RESOLUTION_PRESETS.

## Deve permanecer isolado

SceneManager, TrackManager, MarbleSystem, PathModel/PathEditor, rigs de câmera,
ControlPanel do marble, VariationGenerator do marble, ScenePreset v1.

## Precisa ser generalizado (mínimo)

- App: seleção de gerador (Marble Run | Satisfying Objects) delegando render,
  captura e painel. Marble continua o padrão.
- Persistência: campo opcional `generator` + seção `satisfying` (retrocompatível).

## Regression Risks

- Alterar `ScenePreset`/validador pode invalidar presets antigos → novos campos
  opcionais, migração explícita, testes de presets antigos.
- `App` é central: integração deve ser aditiva; testes existentes (219) e build
  devem continuar passando.
- Tamanho do bundle (three já ~700 KB).

## Visual Quality Requirements (maior impacto → menor)

1. Deformação localizada + bulging + contato coerente (silhueta).
2. Normais corretas da malha deformada (shading revela a deformação).
3. Material (clearcoat/sheen/transmission) × iluminação de estúdio (key/fill/rim/top).
4. Sombras: sombra de contato suave + shadow map macio (evitar flutuação).
5. Câmera macro vertical 1080×1920, objeto protagonista, micro-movimento periódico.
6. Fundo limpo (ciclorama), tone mapping neutro/AgX, sRGB.
7. Subdivisão suficiente (sem facetas) e antialiasing.

## Technical Risks

- Custo de CPU da deformação + upload por frame (mitigação: buffers pré-alocados,
  normais recalculadas in-place; medir).
- Transmission custa uma passada extra; SwiftShader (validação headless) é lento.
- Interpenetração esfera × malha (mitigação: restrição de contato + teste).
- Emenda do loop (mitigação: curva com bordas nulas + teste state(0)==state(1)).

## Recommended Architecture

Estratégia B (ver DECISIONS.md D-001):

    src/satisfying/
      SatisfyingSchema.ts        settings, specs, validação
      SatisfyingGenerator.ts     cena + update(normalizedTime)
      geometry/SoftBlockGeometry.ts
      deformation/SqueezeDeformer.ts
      pressure/PressureTool.ts, SpherePressureTool.ts
      animation/PressureCurve.ts
      materials/SatisfyingMaterials.ts
      lighting/SatisfyingLighting.ts
      camera/MacroCameraRig.ts
      scene/StudioBackdrop.ts, ContactShadow.ts
      presets/SatisfyingPresets.ts
