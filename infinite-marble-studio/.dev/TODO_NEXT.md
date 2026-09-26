# TODO (somente pendências, em ordem)

1. Schema: `generator` + `satisfying` opcionais no ScenePreset (retrocompatível) +
   validação de SatisfyingSettings (rejeitar parâmetros inválidos) + testes.
2. App: seletor de gerador; SqueezeScene renderizada pelo RendererManager existente;
   CaptureHost delega para o gerador ativo (PNG/WebM reaproveitados).
3. Painel Squeeze (lil-gui): Object, Material, Pressure, Deformation, Camera,
   Lighting, Loop — reconstrução incremental (material/luz sem recriar malha).
4. Restaurar shadowMap PCF ao voltar para o Marble Run.
5. Presets: Pink Slime, Yellow Soft Block, Blue Gel, Candy Cube, Dark Rubber,
   Soft Silicone (validar cada um visualmente).
6. Nova Variação do squeeze (≥ 3 categorias + relatório).
7. Batch: seed inicial + quantidade → configs squeeze-<seed> (JSON).
8. Refinamentos visuais: gradiente/vinheta de fundo; esfera com mais definição.
9. Testes restantes da lista 45 (serialização, presets antigos, parâmetros inválidos,
   luzes periódicas, export determinístico) + validação no navegador do app.
10. Documentação (README/ARCHITECTURE) + build:single.
