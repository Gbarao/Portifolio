# TODO (somente pendências, em ordem)

1. Medir FPS do preview em GPU real (1080×1920, preset Blue Gel com transmissão).
   Se < 60 FPS: reduzir subdivisão no preview (qualidade adaptativa) ou portar o
   SqueezeDeformer para vertex shader (a função é pura).
2. Renderização de vídeos em lote (fila sequencial com WebCodecs) — hoje só JSON.
3. Ações futuras (Crush, Stretch, Push, Pinch, Roll) e ferramentas (Plate, Roller…).
4. Refinos visuais opcionais: vinheta sutil no fundo; esfera com leve textura procedural.
