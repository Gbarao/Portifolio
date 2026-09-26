# Validation

Regra: nunca marcar PASS sem ter executado. Cada bloco registra data/sessão.

## Baseline — Session 01 (antes de qualquer alteração do Squeeze)

    TypeScript (npm run typecheck):   PASS
    ESLint (npm run lint):            PASS (0 warnings)
    Prettier (prettier --check .):    PASS
    Vitest (npm test):                PASS — 14 arquivos, 219 testes
    Production Build (npm run build): PASS

## Session 01 — fim da Fase 1 (protótipo visual)

    TypeScript:           PASS
    ESLint:               PASS
    Prettier:             PASS
    Vitest:               PASS — 15 arquivos, 236 testes (219 Marble + 17 Squeeze)
    Production Build:     PASS (dist/ contém apenas index.html; lab fora do build)
    Marble Regression:    PASS (suíte original de 219 testes inalterada e passando)
    Squeeze Determinism:  PASS (src/tests/Squeeze.test.ts: mesma seed → mesma malha/frame)
    Seamless Loop:        PASS (state(0) == state(1); bloco volta exatamente ao repouso)
    Volume:               PASS — erro máximo 1,3 % no ciclo (teste exige < 2 %)
    Contato:              PASS — sem interpenetração, sem gap durante o contato
    Browser Runtime:      PASS — lab/squeeze.html em Chromium headless (SwiftShader),
                          0 erros/avisos no console
    Visual Validation:    PASS (com refinamentos anotados em TODO_NEXT.md)
    Performance (CPU):    deformação+normais 29.548 vértices: ~5,8 ms/frame (Chromium
                          headless), ~7,9 ms (Node). Render em GPU real: NOT RUN.

Capturas: `.dev/validation/phase1-sequence.png` (repouso, 25/50/75/100 %,
recuperação t=0,68 e 0,76) e `phase1-peak-1080x1920.png`.
Script: `.dev/validation/capture-squeeze.cjs` (requer `npx vite --port 5174`).

Avaliação visual (Fase 1):

- Parece macio? Sim — achatamento localizado + bulging em barril + cantos que rolam.
- Sensação de contato? Sim — esfera afunda, superfície conforma, oclusão de contato.
- Volume reage? Sim — medido (erro ≤ 1,3 %).
- Iluminação evidencia a deformação? Sim — clearcoat + RectArea revelam o barril.
- Premium? Bom para MVP; pendentes refinamentos de fundo (gradiente) e da esfera.
