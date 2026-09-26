import GUI, { type Controller } from 'lil-gui';
import {
  LOOP_SPECS,
  OUTPUT_SPECS,
  RESOLUTION_PRESETS,
  type FieldSpec,
  type ResolutionPresetId,
  type ScenePreset,
} from '../presets/PresetSchema';
import { SATISFYING_PRESETS } from '../satisfying/presets/SatisfyingPresets';
import { LIGHTING_LABELS, MATERIAL_LABELS } from '../satisfying/presets/SqueezeVariation';
import {
  CAMERA_SPECS,
  DEFORMATION_SPECS,
  LIGHTING_SPECS,
  MATERIAL_SPECS,
  OBJECT_SPECS,
  PRESSURE_SPECS,
  BACKGROUND_SPECS,
} from '../satisfying/SatisfyingSchema';
import {
  FUTURE_ACTIONS,
  type SatisfyingLightingId,
  type SatisfyingMaterialId,
  type SatisfyingSettings,
} from '../satisfying/SatisfyingSettings';
import { MAX_BATCH_AMOUNT } from '../satisfying/presets/SqueezeBatch';
import { el } from './dom';

export type OutputSection = 'output' | 'loop' | 'seed';

export interface SatisfyingPanelActions {
  /** Configurações do squeeze alteradas (commit = fim da edição → histórico). */
  onChange(commit: boolean): void;
  onProjectChange(sections: OutputSection[], commit: boolean): void;
  loadPreset(name: string): void;
  newVariation(): void;
  randomizeAll(): void;
  applyMaterialType(type: SatisfyingMaterialId): void;
  applyLightingPreset(id: SatisfyingLightingId): void;
  applyResolutionPreset(id: ResolutionPresetId): void;
  exportVideo(): void;
  capturePng(): void;
  exportJson(): void;
  importJson(): void;
  generateBatch(seedStart: number, amount: number): void;
}

const invert = <T extends string>(labels: Record<T, string>): Record<string, T> =>
  Object.fromEntries(Object.entries(labels).map(([k, v]) => [v, k])) as Record<string, T>;

const TOOL_FINISH_LABELS = {
  Cerâmica: 'ceramic',
  'Metal acetinado': 'satinMetal',
  Cromado: 'chrome',
  Vidro: 'glass',
};

/**
 * Painel avançado do gerador Satisfying Objects (Squeeze). Controles derivados das
 * tabelas FieldSpec do schema (mesmos limites da validação de JSON).
 */
export class SatisfyingPanel {
  private gui: GUI | null = null;
  private bound: SatisfyingSettings | null = null;
  private readonly report = el('pre', { className: 'variation-report' });
  private readonly timing = { hold: 0.12, release: 0.16 };
  private readonly ui = {
    preset: SATISFYING_PRESETS[0]?.name ?? '',
    batchStart: 1000,
    batchAmount: 20,
    action: 'Squeeze',
  };

  constructor(
    private readonly container: HTMLElement,
    private readonly actions: SatisfyingPanelActions,
  ) {}

  get root(): HTMLElement | null {
    return this.gui?.domElement ?? null;
  }

  setVisible(visible: boolean): void {
    this.gui?.show(visible);
  }

  setReport(text: string): void {
    this.report.textContent = text;
    this.report.hidden = text.length === 0;
  }

  /** Liga o painel ao projeto; reconstrói se o objeto `satisfying` mudou de identidade. */
  bind(project: ScenePreset): void {
    const settings = project.satisfying;
    if (!settings) return;
    if (SATISFYING_PRESETS.some((p) => p.name === project.name)) this.ui.preset = project.name;
    if (this.gui && this.bound === settings) {
      this.refresh();
      return;
    }
    const wasVisible = this.gui ? this.gui.domElement.style.display !== 'none' : true;
    this.gui?.destroy();
    this.bound = settings;
    this.gui = this.build(project, settings);
    this.gui.show(wasVisible);
  }

  refresh(): void {
    const settings = this.bound;
    if (settings) {
      const t = settings.pressure.timing;
      this.timing.hold = round3(t.holdEnd - t.peak);
      this.timing.release = round3(t.toolReleaseEnd - t.holdEnd);
    }
    for (const c of this.gui?.controllersRecursive() ?? []) c.updateDisplay();
  }

  private build(project: ScenePreset, s: SatisfyingSettings): GUI {
    const gui = new GUI({ container: this.container, title: 'Satisfying Objects · Squeeze' });
    gui.domElement.classList.add('satisfying-gui');
    const change = (c: Controller): Controller =>
      c
        .onChange(() => this.actions.onChange(false))
        .onFinishChange(() => this.actions.onChange(true));
    const num = <T extends object>(
      folder: GUI,
      object: T,
      key: keyof T & string,
      spec: FieldSpec,
      label: string,
      tip: string,
    ): Controller => {
      if (spec.kind !== 'number') throw new Error(`Campo ${key} não é numérico`);
      const c = folder.add(object, key, spec.min, spec.max, spec.step ?? (spec.integer ? 1 : 0.01));
      c.domElement.title = tip;
      return change(c.name(label));
    };
    const color = <T extends object>(
      folder: GUI,
      object: T,
      key: keyof T & string,
      label: string,
    ) => change(folder.addColor(object, key).name(label));
    const button = (folder: GUI, label: string, tip: string, run: () => void): Controller => {
      const c = folder.add({ run }, 'run').name(label);
      c.domElement.title = tip;
      return c;
    };

    // Gerador / ação / presets / variação
    const g = gui.addFolder('1. Squeeze');
    const actionOptions = ['Squeeze', ...FUTURE_ACTIONS.map((a) => `${capitalize(a)} (em breve)`)];
    g.add(this.ui, 'action', actionOptions)
      .name('Ação')
      .onChange((value: string) => {
        if (value !== 'Squeeze') {
          this.ui.action = 'Squeeze';
          this.refresh();
        }
      });
    g.add(
      this.ui,
      'preset',
      SATISFYING_PRESETS.map((p) => p.name),
    ).name('Preset');
    button(g, '▶ Carregar preset', 'Carrega o preset escolhido', () =>
      this.actions.loadPreset(this.ui.preset),
    );
    button(g, '✦ Nova variação', 'Altera 3 ou mais categorias (N)', () =>
      this.actions.newVariation(),
    );
    button(g, '🎲 Tudo aleatório', 'Sorteia todas as categorias (T)', () =>
      this.actions.randomizeAll(),
    );
    g.add(project, 'seed', 0, 4294967295, 1)
      .name('Seed')
      .onChange(() => this.actions.onProjectChange(['seed'], false))
      .onFinishChange(() => this.actions.onProjectChange(['seed'], true));
    g.domElement.append(this.report);
    this.setReport(this.report.textContent ?? '');

    const o = gui.addFolder('2. Objeto');
    num(o, s.object, 'width', OBJECT_SPECS.width, 'Largura', 'Largura do bloco');
    num(o, s.object, 'height', OBJECT_SPECS.height, 'Altura', 'Altura do bloco');
    num(o, s.object, 'depth', OBJECT_SPECS.depth, 'Profundidade', 'Profundidade do bloco');
    num(o, s.object, 'roundness', OBJECT_SPECS.roundness, 'Arredondamento', 'Raio das arestas');
    num(o, s.object, 'subdivision', OBJECT_SPECS.subdivision, 'Subdivisão', 'Densidade da malha');

    const m = gui.addFolder('3. Material');
    m.add(s.material, 'type', invert(MATERIAL_LABELS))
      .name('Tipo')
      .onChange((type: SatisfyingMaterialId) => this.actions.applyMaterialType(type));
    color(m, s.material, 'color', 'Cor');
    num(m, s.material, 'roughness', MATERIAL_SPECS.roughness, 'Rugosidade', 'Rugosidade');
    num(m, s.material, 'metalness', MATERIAL_SPECS.metalness, 'Metalicidade', 'Metalicidade');
    num(m, s.material, 'clearcoat', MATERIAL_SPECS.clearcoat, 'Clearcoat', 'Verniz brilhante');
    num(
      m,
      s.material,
      'clearcoatRoughness',
      MATERIAL_SPECS.clearcoatRoughness,
      'Rug. clearcoat',
      'Rugosidade do verniz',
    );
    num(m, s.material, 'transmission', MATERIAL_SPECS.transmission, 'Transmissão', 'Translucidez');
    num(m, s.material, 'thickness', MATERIAL_SPECS.thickness, 'Espessura', 'Espessura óptica');
    num(m, s.material, 'sheen', MATERIAL_SPECS.sheen, 'Sheen', 'Brilho aveludado');

    const p = gui.addFolder('4. Pressão');
    p.add(s.pressure, 'toolFinish', TOOL_FINISH_LABELS)
      .name('Acabamento')
      .onChange(() => this.actions.onChange(true));
    color(p, s.pressure, 'toolColor', 'Cor da esfera');
    num(p, s.pressure, 'toolRadius', PRESSURE_SPECS.toolRadius, 'Raio da esfera', 'Raio');
    num(
      p,
      s.pressure,
      'strength',
      PRESSURE_SPECS.strength,
      'Força',
      'Profundidade (fração da altura)',
    );
    num(
      p,
      s.pressure,
      'cycles',
      PRESSURE_SPECS.cycles,
      'Pressões por loop',
      'Velocidade (inteiro)',
    );
    num(p, s.pressure, 'approachHeight', PRESSURE_SPECS.approachHeight, 'Altura inicial', 'Folga');
    num(p, s.pressure, 'offsetX', PRESSURE_SPECS.offsetX, 'Deslocamento X', 'Ponto de pressão');
    num(p, s.pressure, 'offsetZ', PRESSURE_SPECS.offsetZ, 'Deslocamento Z', 'Ponto de pressão');
    num(p, s.pressure, 'creep', PRESSURE_SPECS.creep, 'Afundar no hold', 'Fluência');
    const applyTiming = (): void => {
      const t = s.pressure.timing;
      t.holdEnd = round3(Math.min(0.8, t.peak + this.timing.hold));
      t.toolReleaseEnd = round3(Math.min(0.9, t.holdEnd + this.timing.release));
      t.recoveryEnd = round3(Math.min(0.97, Math.max(t.toolReleaseEnd + 0.06, t.holdEnd + 0.3)));
    };
    p.add(this.timing, 'hold', 0.02, 0.25, 0.01)
      .name('Duração do hold')
      .onChange(() => {
        applyTiming();
        this.actions.onChange(false);
      })
      .onFinishChange(() => this.actions.onChange(true));
    p.add(this.timing, 'release', 0.06, 0.25, 0.01)
      .name('Tempo de soltura')
      .onChange(() => {
        applyTiming();
        this.actions.onChange(false);
      })
      .onFinishChange(() => this.actions.onChange(true));
    num(p, s.deformation, 'elasticity', DEFORMATION_SPECS.elasticity, 'Bounce', 'Rebote elástico');

    const d = gui.addFolder('5. Deformação');
    num(d, s.deformation, 'softness', DEFORMATION_SPECS.softness, 'Maciez', 'Compressão do corpo');
    num(d, s.deformation, 'viscosity', DEFORMATION_SPECS.viscosity, 'Viscosidade', 'Memória');
    num(d, s.deformation, 'bulge', DEFORMATION_SPECS.bulge, 'Bulge', 'Expansão lateral');
    num(
      d,
      s.deformation,
      'volumePreservation',
      DEFORMATION_SPECS.volumePreservation,
      'Preservar volume',
      '1 = volume constante',
    );
    num(d, s.deformation, 'falloff', DEFORMATION_SPECS.falloff, 'Falloff', 'Largura da saia');
    num(d, s.deformation, 'locality', DEFORMATION_SPECS.locality, 'Localização', 'Local × global');
    num(d, s.deformation, 'bulgeHeight', DEFORMATION_SPECS.bulgeHeight, 'Altura do bulge', 'Pico');

    const c = gui.addFolder('6. Câmera');
    num(c, s.camera, 'fov', CAMERA_SPECS.fov, 'FOV', 'Campo de visão');
    num(c, s.camera, 'distance', CAMERA_SPECS.distance, 'Distância', '0 = automática');
    num(c, s.camera, 'elevation', CAMERA_SPECS.elevation, 'Altura (°)', 'Elevação');
    num(c, s.camera, 'azimuth', CAMERA_SPECS.azimuth, 'Ângulo (°)', 'Azimute');
    num(c, s.camera, 'targetHeight', CAMERA_SPECS.targetHeight, 'Alvo', 'Altura do alvo');
    num(
      c,
      s.camera,
      'orbitAmplitude',
      CAMERA_SPECS.orbitAmplitude,
      'Órbita (°)',
      'Micro-movimento',
    );
    num(c, s.camera, 'dollyAmplitude', CAMERA_SPECS.dollyAmplitude, 'Respiro', 'Dolly periódico');
    num(c, s.camera, 'cycles', CAMERA_SPECS.cycles, 'Ciclos da câmera', 'Inteiro por loop');
    num(c, s.camera, 'framingMargin', CAMERA_SPECS.framingMargin, 'Margem', 'Enquadramento');

    const l = gui.addFolder('7. Iluminação');
    l.add(s.lighting, 'preset', invert(LIGHTING_LABELS))
      .name('Preset')
      .onChange((id: SatisfyingLightingId) => this.actions.applyLightingPreset(id));
    num(l, s.lighting, 'intensity', LIGHTING_SPECS.intensity, 'Intensidade', 'Geral');
    num(l, s.lighting, 'exposure', LIGHTING_SPECS.exposure, 'Exposição', 'Tone mapping');
    num(l, s.lighting, 'key', LIGHTING_SPECS.key, 'Key', 'Luz principal');
    num(l, s.lighting, 'fill', LIGHTING_SPECS.fill, 'Fill', 'Preenchimento');
    num(l, s.lighting, 'rim', LIGHTING_SPECS.rim, 'Rim', 'Recorte');
    num(l, s.lighting, 'top', LIGHTING_SPECS.top, 'Top', 'Softbox superior');
    num(l, s.lighting, 'environment', LIGHTING_SPECS.environment, 'Ambiente', 'Reflexos');
    num(l, s.lighting, 'shadowSoftness', LIGHTING_SPECS.shadowSoftness, 'Suavidade', 'Sombra');

    const b = gui.addFolder('8. Fundo');
    color(b, s.background, 'color', 'Parede');
    color(b, s.background, 'floorColor', 'Piso');
    num(b, s.background, 'contactShadow', BACKGROUND_SPECS.contactShadow, 'Sombra de contato', '');

    const out = gui.addFolder('9. Loop e exportação');
    out
      .add(
        project.output,
        'resolutionPreset',
        Object.fromEntries(RESOLUTION_PRESETS.map((r) => [r.label, r.id])),
      )
      .name('Formato')
      .onChange((id: ResolutionPresetId) => this.actions.applyResolutionPreset(id));
    const loopSpec = LOOP_SPECS.durationSeconds;
    const outFps = OUTPUT_SPECS.fps;
    if (loopSpec.kind === 'number') {
      out
        .add(project.loop, 'durationSeconds', loopSpec.min, loopSpec.max, 0.5)
        .name('Duração do loop (s)')
        .onChange(() => this.actions.onProjectChange(['loop'], false))
        .onFinishChange(() => this.actions.onProjectChange(['loop'], true));
    }
    if (outFps.kind === 'enum') {
      out
        .add(project.output, 'fps', outFps.values as number[])
        .name('FPS')
        .onChange(() => this.actions.onProjectChange(['output'], true));
    }
    button(out, '⬇ Exportar vídeo (WebM)', 'Grava o loop', () => this.actions.exportVideo());
    button(out, '📷 Capturar PNG', 'Frame atual na resolução final', () =>
      this.actions.capturePng(),
    );
    button(out, '⇩ Exportar JSON', 'Salva o projeto', () => this.actions.exportJson());
    button(out, '⇧ Importar JSON', 'Carrega um projeto', () => this.actions.importJson());

    const batch = gui.addFolder('10. Lote (batch)');
    batch.add(this.ui, 'batchStart', 0, 4294967295, 1).name('Seed inicial');
    batch.add(this.ui, 'batchAmount', 1, MAX_BATCH_AMOUNT, 1).name('Quantidade');
    button(batch, '⬇ Gerar variações (ZIP de JSON)', 'squeeze-<seed>.json reproduzíveis', () =>
      this.actions.generateBatch(this.ui.batchStart, this.ui.batchAmount),
    );

    for (const folder of [d, c, l, b, batch]) folder.close();
    return gui;
  }
}

function round3(value: number): number {
  return Math.round(value * 1000) / 1000;
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
