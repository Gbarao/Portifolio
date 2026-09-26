# Decisões arquiteturais — Satisfying Objects / Squeeze Engine

Registro das decisões importantes. Uma sessão futura NÃO deve reverter uma decisão
sem ler o contexto e as alternativas descartadas.

---

## D-001 — Estratégia B: novo subsistema `src/satisfying/`

Decision:
Implementar Satisfying Objects como subsistema novo e isolado em `src/satisfying/`,
com cena, câmera, luzes, materiais e schema próprios. O Marble Studio (`src/app`,
`src/scene`, `src/track`, `src/marbles`, `src/path`, `src/camera`, `src/presets`)
permanece intacto; só recebe pontos de integração mínimos (seleção de gerador).

Reason:

- `SceneManager`, `LightingManager`, `BackgroundManager` e o `ScenePreset` v1 são
  específicos de trilho + bolinhas (bounds do trajeto, suportes, cúpulas, rigs
  seguindo o trajeto). Generalizá-los criaria acoplamento e risco de regressão.
- O que é genérico já está em módulos independentes e pode ser reutilizado sem
  alteração: `core/LoopClock` (tempo derivado de frameIndex), `core/SeededRandom`
  (Mulberry32 + deriveSeed), `core/PeriodicNoise`, `core/MathUtils`,
  `core/Disposable`, `scene/RendererManager` (preview × export), `export/*`
  (VideoExporter com MediaRecorder / WebCodecs + WebmMuxer / PNG ZIP, ZipWriter,
  FileNaming, ExportValidator), `CaptureHost` (contrato de captura).
- Qualidade visual do squeeze exige iluminação, fundo e câmera próprios
  (macro/produto), diferentes dos rigs do marble.

Alternativas descartadas:

- Estratégia A (estender SceneManager/ScenePreset v1): mistura dois domínios num
  schema já grande; cada ajuste visual do squeeze arriscaria presets antigos.
- Estratégia C (novo renderer/WebGPU): o WebGLRenderer do three r186 +
  MeshPhysicalMaterial atende (clearcoat, sheen, transmission, sombras PCF).
  WebGPU não traz ganho visual relevante para este efeito e reduz compatibilidade
  (inclusive o ambiente de validação headless usa SwiftShader/WebGL).

---

## D-002 — Deformação em buffers de geometria (CPU), não no vertex shader

Decision:
A deformação é uma função analítica pura `deform(restPosition, toolState, params)`
aplicada a cada frame sobre buffers pré-alocados (`Float32Array`), seguida de
recálculo de normais. Não há estado acumulado: o resultado depende só de
`normalizedTime` + seed + settings.

Reason:

- Uma única fonte de verdade: o mesmo código roda no navegador e nos testes
  (NaN/Infinity, volume, contato sem interpenetração, periodicidade).
- Sombras corretas sem duplicar o deslocamento em `customDepthMaterial`.
- Normais exatas da malha deformada (sem aproximação por derivadas no shader).
- Custo medido é compatível com 60 FPS para ~25–60 mil vértices (ver VALIDATION.md).

Alternativas descartadas:

- Vertex shader (`onBeforeCompile`): mais barato, mas exigiria reimplementar a
  deformação em GLSL e em TS (testes), manter o depth material sincronizado e
  aproximar normais por diferenças finitas no shader. Pode ser reavaliado se a
  performance em GPU real for insuficiente (a função é pura e portável).
- Física/soft body acumulativa: não determinística frame a frame e sem loop exato.

---

## D-003 — Geometria: rounded box procedural soldada

Decision:
Cubo subdividido (N×N por face) com vértices compartilhados nas arestas, projetado
para uma caixa arredondada (ponto → caixa interna reduzida + direção × raio).
Malha única indexada e contínua: normais suaves, sem costuras.

Reason: BoxGeometry tem vértices duplicados nas arestas (costura na deformação) e
não tem cantos arredondados; bevel/Extrude gera triangulação irregular no topo.

---

## D-004 — Modelo de deformação (squeeze)

Campo de deslocamento contínuo definido sobre a posição de repouso:

1. Compressão global (coluna sob a ferramenta, decai com distância horizontal).
2. Indentação local com perfil de Hertz fora do contato (C¹ na borda do contato)
   e conformação exata à esfera dentro do contato.
3. Bulging lateral localizado (perfil vertical com pico acima do meio, zero no
   chão, peso gaussiano pela distância ao eixo da ferramenta).
4. Compensação de volume: amplitude do bulging calculada a partir do volume
   deslocado (integração numérica determinística) × `volumePreservation`.
5. Restrição de contato: nenhum vértice dentro da esfera (projeção vertical).
   Detalhes e constantes: `src/satisfying/deformation/SqueezeDeformer.ts`.

---

## D-005 — Curva de pressão por fases com easing, periódica por construção

Fases (fração do ciclo): repouso → aproximação → contato → compressão máxima →
hold → recuperação → repouso. Valores e derivadas nulos nas bordas; oscilação
elástica amortecida multiplicada por janela que zera antes de t = 1.
`state(0) === state(1)` exatamente.

---

## D-006 — Protótipo em página de laboratório só de desenvolvimento

A Fase 1 usa `lab/squeeze.html` (servida pelo `vite dev`, fora do build de
produção) para validação visual e captura de frames, antes de qualquer editor.

---

## D-007 — Sombras VSM no squeeze

Decision: SatisfyingLighting usa `VSMShadowMap` (penumbra larga via blur separável)
e `shadow.intensity = 0.62`; a sombra de contato analítica é tingida com a cor do
piso (nunca cinza).

Reason: PCF com raio em texels produzia penumbra estreita e sombra cinza/pesada.

Consequência: ao alternar para o Marble Run, restaurar `PCFShadowMap`
(`renderer.shadowMap.needsUpdate = true`).

---

## D-008 — Compensação de volume medida na própria malha

Decision: ΔV = Σ Aᵢ nᵢ·dᵢ (áreas por vértice pré-calculadas), incluindo o fator de
estiramento vertical local na área lateral que recebe o bulging.

Reason: estimativa por grade retangular errava ~3,5 % (ignorava arredondamento e a
compressão vertical das laterais). Medido após a mudança: ≤ 1,3 % no ciclo.

Alternativa descartada: relaxar o teste de volume.
