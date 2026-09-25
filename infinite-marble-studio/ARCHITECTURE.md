# Arquitetura

## Decisões críticas

**Preview separado do Export.** O preview precisa de interatividade (tempo real, pausa, velocidade,
resolução adaptada à janela). O export precisa de exatidão: cada frame é uma função pura do índice,
na resolução final. Os dois usam exatamente o mesmo código de cena (`SceneManager.renderAt`) e a
mesma conversão de tempo (`frameToNormalizedTime`). O que muda é só a origem do tempo e o tamanho do
drawing buffer. Por padrão o preview é quantizado à grade de frames, então um frame do preview é
bit a bit o mesmo tempo normalizado do frame correspondente do export.

**`LoopClock` em dois modos.** No modo Preview o tempo é derivado de uma âncora
(`performance.now()`), reancorada em pause, play, velocidade e seek. Não há soma de delta time
frame a frame, só uma função linear por trechos. No modo Export o tempo é `frameIndex / totalFrames`,
sem relógio. Isso elimina deriva numérica e torna o export reproduzível.

**`InstancedMesh` para as bolinhas.** Até 250 bolinhas em **uma** draw call (mais uma no passe de
sombra). A atualização por frame escreve matrizes com `setMatrixAt` usando vetores, quaternion e
matriz temporários fixos (sem alocação), e marca `instanceMatrix.needsUpdate` uma vez por frame.
Cores por instância usam `instanceColor`.

**Camada de simulação sem WebGL.** `Simulation` (trajeto + cinemática + câmera) e
`evaluateLightIntensities` são puros e rodam no Node. O renderizador os consome, e os testes
(`SceneEvaluator.capture`) verificam loop perfeito e determinismo no mesmo código usado em
produção.

**Frames alinhados à gravidade ou por transporte paralelo, em vez de Frenet-Serret puro.** Os
frames de Frenet invertem em pontos de inflexão e ficam indefinidos em trechos retos, o que faria as
bolinhas "pularem" de lado. `PathFrames` escolhe entre dois modos:

- **gravity**, quando nenhum trecho do trajeto é vertical (|tangente·Y| < 0,85): o "para cima" é a
  projeção do eixo Y no plano normal à tangente. É o comportamento de uma pista real: a canaleta
  fica aberta para cima e as bolinhas por cima do trilho, inclusive em bobinas, onde o transporte
  paralelo acumularia torção e giraria a canaleta.
- **transport**, em loops verticais: método da dupla reflexão (frames com rotação mínima), com a
  torção residual distribuída para que `frame(0) = frame(1)` e uma rolagem constante que alinha o
  "para cima" a +Y (ou +Z em curvas verticais planas).

Nos dois modos o frame depende só da tangente naquele ponto, então fecha sem emenda. Trilho,
canaleta, dual rail, hastes e bolinhas usam os mesmos frames: as bolinhas ficam sempre dentro da
canaleta ou centralizadas entre os trilhos.

**Canaleta (groove) extrudada.** Perfil em U (superfície interna, externa e duas bordas, com
vértices separados para arestas nítidas) extrudado ao longo dos frames, com normais analíticas e
UV ao longo do comprimento. A textura de madeira é desenhada por código, periódica no sentido do
comprimento, e repetida um número inteiro de vezes, então não há emenda no fechamento do loop.

**Periodicidade por construção.** Toda grandeza animada é `f(t)` com período 1: senos e cossenos
com número inteiro de ciclos, `modulo(…, 1)` e ruído gradiente periódico (`PeriodicNoise`). Nenhum
estado depende do frame anterior.

**Determinismo por seed.** `SeededRandom` (Mulberry32) com `deriveSeed(seed, "subsistema")` dá
streams independentes: mudar a paleta não altera o trajeto aleatório, por exemplo. O ESLint proíbe
`Math.random`. `SeedSource` é o único ponto não determinístico e só escolhe seeds novas.

**Dois encoders de vídeo.** O MediaRecorder (exigido pela especificação, padrão) carimba cada frame
com o horário real de captura, então só gera timing correto se a renderização acompanhar o tempo
real. O encoder opcional WebCodecs define timestamps explícitos e usa um muxer WebM próprio
(`WebmMuxer.ts`, sem dependências). Com ele a saída tem precisão de frame independente da GPU. O
fallback final é ZIP de PNGs (`ZipWriter.ts`, método STORE).

**Sem framework de UI.** lil-gui para os controles e DOM simples para a tabela de pontos, o
histórico, a barra superior e as sobreposições. O estado do projeto é um único objeto JSON
(`ScenePreset`) cuja identidade é preservada (`assignDeep`), para que os controles fiquem ligados
aos mesmos objetos após undo, carregamento de preset ou variação.

## Fluxo de tempo

```
Preview:  performance.now() ─► LoopClock (âncora, velocidade) ─► frameIndex ─┐
Export:   índice do frame ────► LoopClock (modo export) ───────► frameIndex ─┤
                                                                             ▼
                               normalizedTime = frameIndex / totalFrames ∈ [0, 1)
                                                                             │
                     animationTime = modulo(normalizedTime × loop.cycleCount, 1)
                                                                             │
      ┌──────────────────────┬───────────────────────┬──────────────────────┤
      ▼                      ▼                       ▼                      ▼
 bolinhas: u = modulo(  câmera (rig):          luzes: pulsação       cores/escala:
 dir·t·ciclos + i/n +   órbita/trilho/follow   com ciclos inteiros   matiz e pulsação
 fase, 1) → getPointAt  com ciclos inteiros                          periódicas
```

## Fluxo de mudanças

```
Controle da GUI / tabela / gizmo / atalho
        │ onChange (ao vivo)                 onFinishChange (commit)
        ▼                                            ▼
App.onSettingsChanged(seções) ── path/track ─► debounce 100 ms ─► SceneManager.applyChanges
        │                     └─ outras ─────► próximo frame ───► SceneManager.applyChanges
        ├─► rascunho automático (debounce 500 ms, localStorage)
        └─► History.push(snapshot JSON)  (até 50 passos; undo/redo reaplicam o projeto)
```

`SceneManager.applyChanges` reconstrói apenas o necessário: o trajeto refaz curva, frames, trilho,
cinemática e handles. A geometria do trilho só é refeita quando mudam estilo, raio, largura ou
segmentos (mudanças de material são aplicadas no lugar). Quantidade ou segmentos das bolinhas
recriam o `InstancedMesh`; o resto só troca a cinemática. Geometrias e materiais substituídos são
descartados com `.dispose()`.

## Fluxo de exportação

```
validateExport (checklist) ─► beginCapture: oculta GUI/helpers, buffer na resolução final,
                              LoopClock em modo export, verifica helpers/GUI ocultos
     ─► para frameIndex = 0 … totalFrames − 1:
            renderExportFrame(i) ─► MediaRecorder (requestFrame, ritmo por rAF)
                                  └► ou WebCodecs (VideoFrame com timestamp exato)
                                  └► ou PNG → ZIP
     ─► endCapture: restaura preview ─► download (Blob + <a download>) ─► histórico
```

## Árvore de arquivos

```
index.html                        Estrutura da página (raiz do Vite)
package.json / package-lock.json  Versões exatas das dependências
vite.config.ts                    Build (base relativa, sourcemaps)
vitest.config.ts                  Testes e limites de cobertura (70%)
tsconfig.json                     TypeScript strict
eslint.config.js                  ESLint flat config (+ proibição de Math.random)
prettier.config.js                Formatação
docs/                             Capturas de tela usadas no README

src/main.ts                       Entry point e tela de erro fatal
src/app/App.ts                    Orquestrador: estado, cena, relógio, UI, persistência, exportação
src/app/AppState.ts               Estado global (singleton) + assignDeep
src/app/EventBus.ts               Emissor de eventos tipado
src/app/ErrorHandler.ts           Tratamento centralizado de erros
src/app/SimplePace.ts             Duração no modo simples preservando a velocidade das bolinhas

src/core/LoopClock.ts             Relógio preview/export, conversões de frame e tempo de animação
src/core/SeededRandom.ts          Mulberry32, derivação de seeds, hash
src/core/SeedSource.ts            Única fonte de seeds novas (crypto.getRandomValues)
src/core/PeriodicNoise.ts         Ruído gradiente 1D periódico com seed
src/core/MathUtils.ts             modulo, clamp, lerp, arredondamento etc.
src/core/Debounce.ts              debounce com flush/cancel
src/core/History.ts               Pilha desfazer/refazer (limite 50)
src/core/Disposable.ts            Interface e liberação de recursos Three.js
src/core/PerformanceMonitor.ts    FPS (janela de 60 frames), níveis e recomendações

src/path/PathModel.ts             CatmullRomCurve3 + frames + bounding sphere/box
src/path/PathFrames.ts            Frames de transporte paralelo, fechados e sem inversão
src/path/PathFactory.ts           Presets procedurais, randomizador e AutoFitPath
src/path/PathValidator.ts         Validação (mínimo de pontos, duplicados, NaN, tamanho, ângulos)
src/path/PathEditor.ts            Operações puras: adicionar, duplicar, mover, remover
src/path/PathHandles.ts           Esferas de controle, TransformControls e seleção por clique

src/track/TrackBuilder.ts         Interface, fábrica, material físico e raio externo do trilho
src/track/GrooveTrackBuilder.ts   Canaleta em U extrudada ao longo dos frames
src/track/TubeTrackBuilder.ts     Tubo contínuo (TubeGeometry)
src/track/DualRailTrackBuilder.ts Dois trilhos paralelos (curvas deslocadas pelos frames)
src/track/TrackManager.ts         Reconstrução e descarte da geometria e da textura do trilho
src/track/WoodTexture.ts          Veios de madeira procedurais (periódicos, sem emenda)
src/track/SupportBuilder.ts       Hastes de suporte (layout determinístico + InstancedMesh)

src/marbles/MarbleKinematics.ts   Fase, u, altura de repouso, rotação, cor (função pura de t)
src/marbles/MarbleSystem.ts       InstancedMesh e atualização sem alocação
src/marbles/MarbleMaterial.ts     Material e textura procedural listrada
src/marbles/MarbleColorPalette.ts Paletas e escalas derivadas da seed

src/camera/CameraRig.ts           Interface, pose, enquadramento automático, suavização
src/camera/FixedCameraRig.ts      Câmera fixa
src/camera/OrbitCameraRig.ts      Órbita com ciclos inteiros
src/camera/FollowCameraRig.ts     Acompanha uma bolinha (suavização por janela)
src/camera/RailCameraRig.ts       Percorre o trilho com a mesma parametrização u
src/camera/TopViewCameraRig.ts    Visão superior
src/camera/CameraFactory.ts       Fábrica, rótulos e padrões por modo

src/scene/Simulation.ts           Modelo matemático da cena (sem WebGL)
src/scene/SceneStateCapture.ts    Captura numérica do estado (testes de loop e determinismo)
src/scene/SceneManager.ts         Cena Three.js, câmeras, helpers, aplicação de mudanças
src/scene/RendererManager.ts      WebGLRenderer, letterbox, preview × resolução de export
src/scene/LightingManager.ts      Hemisphere, principal, fill, rim, sombras, ambiente
src/scene/BackgroundManager.ts    Cor/gradiente/padrão, névoa e chão
src/scene/DecorationManager.ts    Cúpulas decorativas no chão (posições pela seed)

src/presets/PresetSchema.ts       Tipos, specs de campos (validação e UI), limites
src/presets/PresetValidator.ts    Validação, migração v0 → v1 e (de)serialização
src/presets/PresetStore.ts        localStorage: presets do usuário e rascunho
src/presets/DefaultPresets.ts     Padrões, 5 presets de iluminação, 5 cenas built-in
src/presets/VariationGenerator.ts Nova variação/randomizações com relatório

src/export/ExportValidator.ts     Checklist pré-export e plano (duração, frames)
src/export/VideoExporter.ts       MediaRecorder, WebCodecs e fallback ZIP
src/export/WebmMuxer.ts           Muxer/leitor WebM mínimo (EBML)
src/export/ZipWriter.ts           ZIP STORE + CRC-32
src/export/ImageExporter.ts       PNG na resolução final
src/export/ExportHistory.ts       Histórico das 10 últimas exportações
src/export/FileNaming.ts          Nomes de arquivo padronizados
src/export/DownloadUtils.ts       Download de Blob, toBlob e miniaturas
src/export/CaptureHost.ts         Contrato entre exportadores e App

src/ui/ControlPanel.ts            lil-gui em 10 seções, com dicas e visibilidade por modo
src/ui/SimplePanel.ts             Modo simples: estilo, formato, duração e baixar
src/ui/TopBar.ts                  Barra de ações
src/ui/StatusPanel.ts             FPS, draw calls, memória, curva, arquivo
src/ui/PointTable.ts              Tabela de pontos de controle
src/ui/KeyboardShortcuts.ts       Tabela única de atalhos + listener
src/ui/ShortcutsDialog.ts         Diálogo "?"
src/ui/ExportProgress.ts          Progresso, cancelar, re-gravar
src/ui/HistoryPanel.ts            Lista do histórico
src/ui/SafeAreaOverlay.ts         Guia de área segura (20%)
src/ui/Notifier.ts                Mensagens (toasts)
src/ui/dom.ts                     Utilitários de DOM e formatação

src/styles/main.css               Layout base
src/styles/ui.css                 Componentes e tema do lil-gui
src/styles/responsive.css         Telas menores e toque (alvos ≥ 44 px)

src/tests/*.test.ts               Vitest (ambiente Node)
```

## Ajustes em relação à estrutura sugerida

- `index.html` fica na raiz do projeto porque é a raiz que o Vite usa por padrão.
- Arquivos adicionais, cada um com uma responsabilidade que não cabia nos módulos sugeridos sem
  misturar camadas:
  - `Simulation.ts` e `SceneStateCapture.ts`: lógica testável sem WebGL.
  - `PathFrames.ts`: frames estáveis e fechados.
  - `MarbleKinematics.ts`: cinemática pura, compartilhada por renderização, câmera e testes.
  - `WebmMuxer.ts` e `ZipWriter.ts`: formatos de arquivo sem dependências externas.
  - `History.ts`, `Debounce.ts`, `SeedSource.ts` e `PeriodicNoise.ts`: utilitários de núcleo.
  - `TrackManager.ts`, `PathEditor.ts` e `VariationGenerator.ts`.
- Campos além do schema mínimo da especificação (ex.: `railRadius`, `bankAngle`, `encoder`,
  `environmentIntensity`) são **opcionais** na validação: um JSON escrito apenas com os campos
  do schema original continua sendo aceito, e os demais recebem valores padrão.
