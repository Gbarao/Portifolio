import GUI, { type Controller } from 'lil-gui';
import { CAMERA_MODE_LABELS } from '../camera/CameraFactory';
import { MAX_PREVIEW_SPEED, MIN_PREVIEW_SPEED } from '../core/LoopClock';
import { PALETTE_LABELS } from '../marbles/MarbleColorPalette';
import { PATH_PRESET_LABELS } from '../path/PathFactory';
import type { PathValidationResult } from '../path/PathValidator';
import { LIGHTING_PRESET_LABELS } from '../presets/DefaultPresets';
import {
  BACKGROUND_SPECS,
  CAMERA_SPECS,
  LIGHTING_SPECS,
  LOOP_SPECS,
  MARBLE_SPECS,
  OUTPUT_SPECS,
  PATH_SPECS,
  RESOLUTION_PRESETS,
  SHADOW_RESOLUTIONS,
  TRACK_SPECS,
  type CameraMode,
  type FieldSpec,
  type LightingPresetId,
  type PathPresetId,
  type ResolutionPresetId,
  type ScenePreset,
  type SectionKey,
  type Vec3Like,
} from '../presets/PresetSchema';
import type { DirtySection } from '../scene/SceneManager';
import type { RuntimeState } from '../app/AppState';
import { el } from './dom';
import { HistoryPanel, type HistoryPanelActions } from './HistoryPanel';
import { PointTable, type PointTableActions } from './PointTable';

export interface ControlPanelActions {
  onChange(sections: DirtySection[], commit: boolean): void;
  newVariation(): void;
  applyPathPreset(id: PathPresetId): void;
  addPoint(): void;
  duplicatePoint(): void;
  removeSelectedPoint(): void;
  randomizePath(): void;
  autoFitPath(): void;
  pointTable: PointTableActions;
  applyCameraMode(mode: CameraMode): void;
  fitCameraNow(): void;
  setPortrait(): void;
  setEditorView(enabled: boolean): void;
  applyLightingPreset(id: Exclude<LightingPresetId, 'custom'>): void;
  setPlaying(playing: boolean): void;
  setPreviewSpeed(speed: number): void;
  seek(normalizedTime: number): void;
  applyResolutionPreset(id: ResolutionPresetId): void;
  exportVideo(): void;
  capturePng(): void;
  verifyDeterminism(): void;
  setSafeArea(visible: boolean): void;
  setPixelRatio(ratio: number): void;
  setPreviewAtExportResolution(enabled: boolean): void;
  history: HistoryPanelActions;
  savePreset(name: string): void;
  loadPreset(key: string): void;
  deletePreset(key: string): void;
  exportJson(): void;
  importJson(): void;
  restoreDefaults(): void;
  resetSection(section: SectionKey): void;
  getPresetOptions(): Record<string, string>;
}

const MAX_CUSTOM_COLORS = 6;

type CameraKey = keyof ScenePreset['camera'];

/** Quais controles de câmera aparecem em cada modo. */
const CAMERA_VISIBILITY: Partial<
  Record<CameraKey | 'positionFolder' | 'targetFolder', CameraMode[]>
> = {
  distance: ['orbit', 'follow', 'topView'],
  height: ['orbit', 'follow', 'rail'],
  offsetLateral: ['follow', 'rail'],
  cycleCount: ['orbit', 'rail'],
  smoothing: ['follow', 'rail'],
  autoFrame: ['fixed', 'orbit', 'topView'],
  framingMargin: ['fixed', 'orbit', 'topView'],
  followMarbleIndex: ['follow'],
  railLookAhead: ['rail'],
  railPhaseOffset: ['rail'],
  positionFolder: ['fixed'],
  targetFolder: ['fixed', 'orbit', 'topView'],
};

/** Painel lil-gui organizado nas 10 seções da especificação. */
export class ControlPanel {
  readonly gui: GUI;
  readonly pointTable: PointTable;
  readonly historyPanel: HistoryPanel;
  private readonly ui = {
    fps: '–',
    marbles: '',
    loop: '',
    time: 0,
    playing: true,
    speed: 1,
    pixelRatio: 1,
    safeArea: false,
    previewExportRes: false,
    editorView: false,
    presetName: '',
    presetKey: '',
    customCount: 4,
    colors: [0xff6b6b, 0xffd93d, 0x6bcb77, 0x4d96ff, 0xffffff, 0x000000] as number[],
  };
  private readonly colorProxy: Record<string, number> = {};
  private readonly customColorControllers: Controller[] = [];
  private customCountController!: Controller;
  private readonly cameraControllers = new Map<string, { show(v: boolean): void }>();
  private readonly trackControllers: Record<'radius' | 'railDistance' | 'railRadius', Controller>;
  private bgGradientControllers: Controller[] = [];
  private bgPatternControllers: Controller[] = [];
  private fogLinear: Controller[] = [];
  private fogExp: Controller[] = [];
  private fogColor!: Controller;
  private spinCyclesController!: Controller;
  private widthController!: Controller;
  private heightController!: Controller;
  private lightingPresetController!: Controller;
  private presetSelect!: Controller;
  private readonly pathStatus = el('div', { className: 'path-status', 'aria-live': 'polite' });
  private readonly variationReport = el('pre', { className: 'variation-report' });
  private readonly exportInfo = el('div', { className: 'export-info' });
  private readonly folders: GUI[] = [];

  constructor(
    container: HTMLElement,
    private readonly project: ScenePreset,
    private readonly runtime: RuntimeState,
    private readonly actions: ControlPanelActions,
    exportProgressElement: HTMLElement,
  ) {
    this.gui = new GUI({ container, title: 'Infinite Marble Studio' });
    this.pointTable = new PointTable(actions.pointTable);
    this.historyPanel = new HistoryPanel(actions.history);
    this.buildProject();
    this.buildPath();
    this.trackControllers = this.buildTrack();
    this.buildMarbles();
    this.buildCamera();
    this.buildLighting();
    this.buildBackground();
    this.buildLoop();
    this.buildExport(exportProgressElement);
    this.buildPresets();
    // Seções menos usadas começam recolhidas para caber em telas menores.
    for (const folder of this.folders.slice(5)) folder.close();
    this.refresh();
  }

  // ---------------------------------------------------------------- helpers

  private tip<C extends Controller>(controller: C, text: string): C {
    controller.domElement.title = text;
    return controller;
  }

  private folder(parent: GUI, title: string, tip: string): GUI {
    const folder = parent.addFolder(title);
    folder.$title.title = tip;
    if (parent === this.gui) this.folders.push(folder);
    return folder;
  }

  private bindChange(
    controller: Controller,
    sections: DirtySection[],
    before?: () => void,
  ): Controller {
    controller.onChange(() => {
      before?.();
      this.actions.onChange(sections, false);
    });
    controller.onFinishChange(() => this.actions.onChange(sections, true));
    return controller;
  }

  private num<T extends object>(
    folder: GUI,
    object: T,
    key: keyof T & string,
    spec: FieldSpec,
    label: string,
    tip: string,
    sections: DirtySection[],
    before?: () => void,
  ): Controller {
    if (spec.kind !== 'number') throw new Error(`Campo ${key} não é numérico`);
    const step = spec.step ?? (spec.integer ? 1 : 0.01);
    const controller = folder.add(object, key, spec.min, spec.max, step).name(label);
    return this.bindChange(this.tip(controller, tip), sections, before);
  }

  private bool<T extends object>(
    folder: GUI,
    object: T,
    key: keyof T & string,
    label: string,
    tip: string,
    sections: DirtySection[],
    before?: () => void,
  ): Controller {
    return this.bindChange(this.tip(folder.add(object, key).name(label), tip), sections, before);
  }

  private select<T extends object>(
    folder: GUI,
    object: T,
    key: keyof T & string,
    options: Record<string, string | number>,
    label: string,
    tip: string,
    sections: DirtySection[],
    before?: () => void,
  ): Controller {
    return this.bindChange(
      this.tip(folder.add(object, key, options).name(label), tip),
      sections,
      before,
    );
  }

  private color<T extends object>(
    folder: GUI,
    object: T,
    key: keyof T & string,
    label: string,
    tip: string,
    sections: DirtySection[],
    before?: () => void,
  ): Controller {
    return this.bindChange(
      this.tip(folder.addColor(object, key).name(label), tip),
      sections,
      before,
    );
  }

  private vec3(
    parent: GUI,
    title: string,
    vector: Vec3Like,
    range: number,
    tip: string,
    sections: DirtySection[],
    before?: () => void,
  ): GUI {
    const folder = this.folder(parent, title, tip);
    for (const axis of ['x', 'y', 'z'] as const) {
      this.num(
        folder,
        vector,
        axis,
        { kind: 'number', min: -range, max: range, step: 0.1 },
        axis.toUpperCase(),
        `${tip} (${axis.toUpperCase()})`,
        sections,
        before,
      );
    }
    folder.close();
    return folder;
  }

  private action(folder: GUI, label: string, tip: string, run: () => void): Controller {
    return this.tip(folder.add({ run }, 'run').name(label), tip);
  }

  private resetButton(folder: GUI, section: SectionKey): void {
    this.action(folder, '↺ Restaurar grupo', 'Restaura os valores padrão deste grupo', () =>
      this.actions.resetSection(section),
    );
  }

  private invert<T extends string>(labels: Record<T, string>): Record<string, T> {
    return Object.fromEntries(Object.entries(labels).map(([k, v]) => [v, k])) as Record<string, T>;
  }

  // ---------------------------------------------------------------- seções

  private buildProject(): void {
    const f = this.folder(this.gui, '1. Projeto', 'Nome, seed e informações do projeto');
    this.bindChange(
      this.tip(
        f.add(this.project, 'name').name('Nome'),
        'Nome do projeto (usado nos arquivos exportados)',
      ),
      [],
    );
    const seed = this.tip(
      f.add(this.project, 'seed').name('Seed'),
      'Seed determinística: mesma seed + mesmas configurações = mesmo resultado',
    );
    this.bindChange(seed, ['seed']);
    this.tip(
      f.add(this.ui, 'fps').name('FPS atual').listen().disable(),
      'Média de FPS dos últimos 60 frames',
    );
    this.tip(
      f.add(this.ui, 'marbles').name('Bolinhas').listen().disable(),
      'Quantidade de bolinhas',
    );
    this.tip(f.add(this.ui, 'loop').name('Loop').listen().disable(), 'Duração do loop');
    this.action(f, '✦ Nova variação (N)', 'Gera nova seed e altera pelo menos 3 categorias', () =>
      this.actions.newVariation(),
    );
    f.$children.append(this.variationReport);
  }

  private buildPath(): void {
    const f = this.folder(this.gui, '2. Trajeto', 'Formato do percurso e pontos de controle');
    const p = this.project.path;
    this.tip(
      f.add(p, 'preset', this.invert(PATH_PRESET_LABELS)).name('Preset'),
      'Presets procedurais (todos fechados e válidos)',
    ).onChange((id: PathPresetId) => this.actions.applyPathPreset(id));
    this.action(f, '+ Adicionar ponto', 'Insere um ponto após o selecionado', () =>
      this.actions.addPoint(),
    );
    this.action(f, '⧉ Duplicar ponto (Ctrl+D)', 'Duplica o ponto selecionado', () =>
      this.actions.duplicatePoint(),
    );
    this.action(f, '✕ Remover ponto (Delete)', 'Remove o ponto selecionado (mínimo 4)', () =>
      this.actions.removeSelectedPoint(),
    );
    this.action(
      f,
      '🎲 Randomizar trajeto (Shift+T)',
      'Gera 8–20 pontos a partir de uma nova seed',
      () => this.actions.randomizePath(),
    );
    this.action(f, '⤢ AutoFitPath', 'Centraliza em (0,0,0) e escala para caber em raio 5', () =>
      this.actions.autoFitPath(),
    );
    this.bool(f, p, 'closed', 'Fechada', 'Curva fechada (obrigatório para exportar)', ['path']);
    this.select(
      f,
      p,
      'curveType',
      { Centripetal: 'centripetal', Chordal: 'chordal', 'Catmull-Rom': 'catmullrom' },
      'Tipo de curva',
      'Parametrização da Catmull-Rom (centripetal evita laços)',
      ['path'],
    );
    this.num(
      f,
      p,
      'tension',
      PATH_SPECS.tension,
      'Tensão',
      'Tensão da curva (efetiva apenas no tipo Catmull-Rom)',
      ['path'],
    );
    this.resetButton(f, 'path');
    f.$children.append(this.pathStatus, this.pointTable.element);
  }

  private buildTrack(): Record<'radius' | 'railDistance' | 'railRadius', Controller> {
    const f = this.folder(this.gui, '3. Trilho', 'Estilo, dimensões e material do trilho');
    const t = this.project.track;
    this.select(
      f,
      t,
      'style',
      { Tubo: 'tube', 'Dual rail': 'dualRail' },
      'Estilo',
      'Tubo contínuo ou dois trilhos paralelos',
      ['track'],
      () => this.refreshVisibility(),
    );
    const radius = this.num(
      f,
      t,
      'radius',
      TRACK_SPECS.radius,
      'Raio do tubo',
      'Espessura do tubo contínuo',
      ['track'],
    );
    const railDistance = this.num(
      f,
      t,
      'railDistance',
      TRACK_SPECS.railDistance,
      'Largura',
      'Distância entre os dois trilhos',
      ['track'],
    );
    const railRadius = this.num(
      f,
      t,
      'railRadius',
      TRACK_SPECS.railRadius,
      'Raio do trilho',
      'Espessura de cada trilho',
      ['track'],
    );
    this.num(
      f,
      t,
      'bankAngle',
      TRACK_SPECS.bankAngle,
      'Inclinação (°)',
      'Gira o trilho e as bolinhas em torno da tangente',
      ['track'],
    );
    this.color(f, t, 'color', 'Cor', 'Cor do trilho', ['track']);
    this.num(f, t, 'metalness', TRACK_SPECS.metalness, 'Metalness', 'Aparência metálica (0–1)', [
      'track',
    ]);
    this.num(f, t, 'roughness', TRACK_SPECS.roughness, 'Roughness', 'Rugosidade (0 = espelhado)', [
      'track',
    ]);
    this.color(f, t, 'emissive', 'Emissive', 'Cor emissiva (brilho próprio)', ['track']);
    this.num(
      f,
      t,
      'emissiveIntensity',
      TRACK_SPECS.emissiveIntensity,
      'Intensidade emissiva',
      'Intensidade da cor emissiva',
      ['track'],
    );
    this.num(f, t, 'opacity', TRACK_SPECS.opacity, 'Opacidade', 'Transparência do trilho', [
      'track',
    ]);
    this.num(
      f,
      t,
      'segmentCount',
      TRACK_SPECS.segmentCount,
      'Segmentos',
      'Segmentos ao longo da curva (32–400)',
      ['track'],
    );
    this.num(
      f,
      t,
      'radialSegments',
      TRACK_SPECS.radialSegments,
      'Segmentos radiais',
      'Resolução da seção circular',
      ['track'],
    );
    this.bool(f, t, 'visible', 'Visível', 'Mostrar o trilho', ['track']);
    this.bool(f, t, 'castShadow', 'Projeta sombra', 'O trilho projeta sombras', ['track']);
    this.bool(f, t, 'receiveShadow', 'Recebe sombra', 'O trilho recebe sombras', ['track']);
    this.resetButton(f, 'track');
    return { radius, railDistance, railRadius };
  }

  private buildMarbles(): void {
    const f = this.folder(
      this.gui,
      '4. Bolinhas',
      'Quantidade, movimento e aparência das bolinhas',
    );
    const m = this.project.marbles;
    this.num(
      f,
      m,
      'count',
      MARBLE_SPECS.count,
      'Quantidade',
      'Número de bolinhas (1–250), todas em um único InstancedMesh',
      ['marbles'],
    );
    this.num(f, m, 'radius', MARBLE_SPECS.radius, 'Raio', 'Raio das bolinhas', ['marbles']);
    this.num(
      f,
      m,
      'spacing',
      MARBLE_SPECS.spacing,
      'Espaçamento',
      '0 = distribuição uniforme; >0 = fração da curva entre bolinhas',
      ['marbles'],
    );
    this.num(
      f,
      m,
      'cycleCount',
      MARBLE_SPECS.cycleCount,
      'Velocidade (voltas)',
      'Voltas completas por ciclo (inteiro): define a velocidade',
      ['marbles'],
    );
    this.select(
      f,
      m,
      'direction',
      { 'Para frente': 1, 'Para trás': -1 },
      'Direção',
      'Sentido do movimento',
      ['marbles'],
    );
    this.num(
      f,
      m,
      'phaseInitial',
      MARBLE_SPECS.phaseInitial,
      'Fase inicial',
      'Deslocamento inicial ao longo da curva (0–1)',
      ['marbles'],
    );
    this.select(
      f,
      m,
      'palette',
      this.invert(PALETTE_LABELS),
      'Paleta',
      'Paleta de cores (cores derivadas da seed)',
      ['marbles'],
      () => this.refreshVisibility(),
    );
    this.customCountController = this.num(
      f,
      this.ui,
      'customCount',
      { kind: 'number', min: 1, max: MAX_CUSTOM_COLORS, step: 1, integer: true },
      'Cores custom',
      'Quantidade de cores da paleta custom',
      ['marbles'],
      () => this.writeCustomColors(),
    );
    for (let i = 0; i < MAX_CUSTOM_COLORS; i++) {
      const key = `c${i}`;
      this.colorProxy[key] = this.ui.colors[i] ?? 0xffffff;
      this.customColorControllers.push(
        this.color(
          f,
          this.colorProxy,
          key,
          `Cor ${i + 1}`,
          `Cor custom ${i + 1} (aplicada em sequência)`,
          ['marbles'],
          () => this.writeCustomColors(),
        ),
      );
    }
    this.num(f, m, 'metalness', MARBLE_SPECS.metalness, 'Metalness', 'Aparência metálica', [
      'marbles',
    ]);
    this.num(f, m, 'roughness', MARBLE_SPECS.roughness, 'Roughness', 'Rugosidade (0 = espelhado)', [
      'marbles',
    ]);
    this.color(f, m, 'emissive', 'Emissive', 'Cor emissiva', ['marbles']);
    this.num(
      f,
      m,
      'emissiveIntensity',
      MARBLE_SPECS.emissiveIntensity,
      'Intensidade emissiva',
      'Brilho próprio (0–2)',
      ['marbles'],
    );
    this.num(
      f,
      m,
      'scaleVariation',
      MARBLE_SPECS.scaleVariation,
      'Variação de escala',
      'Variação individual ±10% (derivada da seed)',
      ['marbles'],
    );
    this.select(
      f,
      m,
      'pattern',
      { Sólida: 'solid', Listrada: 'striped' },
      'Padrão',
      'Listras tornam a rotação visível',
      ['marbles'],
    );
    this.bool(
      f,
      m,
      'spinAuto',
      'Rotação automática',
      'Calcula voltas inteiras de rotação a partir do percurso',
      ['marbles'],
      () => this.refreshVisibility(),
    );
    this.spinCyclesController = this.num(
      f,
      m,
      'spinCycles',
      MARBLE_SPECS.spinCycles,
      'Rotações (inteiro)',
      'Rotações completas por ciclo',
      ['marbles'],
    );
    this.num(
      f,
      m,
      'hueShiftCycles',
      MARBLE_SPECS.hueShiftCycles,
      'Ciclos de matiz',
      'Rotação periódica das cores (0 = desligado)',
      ['marbles'],
    );
    this.num(
      f,
      m,
      'pulseAmount',
      MARBLE_SPECS.pulseAmount,
      'Pulsação',
      'Amplitude da pulsação de tamanho',
      ['marbles'],
    );
    this.num(
      f,
      m,
      'pulseCycles',
      MARBLE_SPECS.pulseCycles,
      'Ciclos de pulsação',
      'Pulsações por ciclo (inteiro)',
      ['marbles'],
    );
    this.num(
      f,
      m,
      'offsetLateral',
      MARBLE_SPECS.offsetLateral,
      'Offset lateral',
      'Deslocamento lateral em relação ao trilho',
      ['marbles'],
    );
    this.num(
      f,
      m,
      'offsetVertical',
      MARBLE_SPECS.offsetVertical,
      'Offset vertical',
      'Deslocamento vertical em relação ao trilho',
      ['marbles'],
    );
    this.num(f, m, 'segments', MARBLE_SPECS.segments, 'Segmentos', 'Resolução da esfera', [
      'marbles',
    ]);
    this.bool(f, m, 'castShadow', 'Projeta sombra', 'As bolinhas projetam sombras', ['marbles']);
    this.bool(f, m, 'receiveShadow', 'Recebe sombra', 'As bolinhas recebem sombras', ['marbles']);
    this.resetButton(f, 'marbles');
  }

  private buildCamera(): void {
    const f = this.folder(this.gui, '5. Câmera', 'Modo e parâmetros da câmera (todos periódicos)');
    const c = this.project.camera;
    this.tip(
      f.add(c, 'mode', this.invert(CAMERA_MODE_LABELS)).name('Modo'),
      'Fixa, órbita, acompanhar bolinha, na pista ou visão superior',
    ).onChange((mode: CameraMode) => this.actions.applyCameraMode(mode));
    const reg = (key: string, controller: { show(v: boolean): void }): void => {
      this.cameraControllers.set(key, controller);
    };
    this.num(
      f,
      c,
      'fov',
      CAMERA_SPECS.fov,
      'FOV',
      'Campo de visão vertical (20–100°); zoom na visão superior',
      ['camera'],
    );
    reg(
      'distance',
      this.num(
        f,
        c,
        'distance',
        CAMERA_SPECS.distance,
        'Distância',
        'Órbita: raio; Follow: distância atrás; Superior: altitude',
        ['camera'],
      ),
    );
    reg(
      'height',
      this.num(f, c, 'height', CAMERA_SPECS.height, 'Altura', 'Offset vertical da câmera', [
        'camera',
      ]),
    );
    reg(
      'offsetLateral',
      this.num(
        f,
        c,
        'offsetLateral',
        CAMERA_SPECS.offsetLateral,
        'Offset lateral',
        'Deslocamento lateral (câmera "ombro")',
        ['camera'],
      ),
    );
    reg(
      'cycleCount',
      this.num(
        f,
        c,
        'cycleCount',
        CAMERA_SPECS.cycleCount,
        'Ciclos da câmera',
        'Voltas inteiras da câmera por ciclo',
        ['camera'],
      ),
    );
    reg(
      'smoothing',
      this.num(
        f,
        c,
        'smoothing',
        CAMERA_SPECS.smoothing,
        'Suavização',
        'Suavização determinística (janela ao longo da curva)',
        ['camera'],
      ),
    );
    reg(
      'followMarbleIndex',
      this.num(
        f,
        c,
        'followMarbleIndex',
        CAMERA_SPECS.followMarbleIndex,
        'Bolinha alvo',
        'Índice da bolinha acompanhada',
        ['camera'],
      ),
    );
    reg(
      'railLookAhead',
      this.num(
        f,
        c,
        'railLookAhead',
        CAMERA_SPECS.railLookAhead,
        'Olhar à frente',
        'Distância (fração da curva) do ponto observado',
        ['camera'],
      ),
    );
    reg(
      'railPhaseOffset',
      this.num(
        f,
        c,
        'railPhaseOffset',
        CAMERA_SPECS.railPhaseOffset,
        'Offset de fase',
        'Adiantada (+) ou atrasada (−) em relação às bolinhas',
        ['camera'],
      ),
    );
    this.num(
      f,
      c,
      'tilt',
      CAMERA_SPECS.tilt,
      'Inclinação (°)',
      'Inclinação adicional da câmera (−90° a +90°)',
      ['camera'],
    );
    reg(
      'autoFrame',
      this.bool(
        f,
        c,
        'autoFrame',
        'Enquadramento automático',
        'Ajusta a distância conforme a proporção da saída',
        ['camera'],
        () => this.refreshVisibility(),
      ),
    );
    reg(
      'framingMargin',
      this.num(
        f,
        c,
        'framingMargin',
        CAMERA_SPECS.framingMargin,
        'Margem',
        'Margem do enquadramento automático (0–0.3)',
        ['camera'],
      ),
    );
    this.num(
      f,
      c,
      'swayAmount',
      CAMERA_SPECS.swayAmount,
      'Balanço',
      'Balanço orgânico com ruído periódico (fecha o loop)',
      ['camera'],
    );
    reg(
      'positionFolder',
      this.vec3(f, 'Posição (fixa)', c.position, 100, 'Posição da câmera fixa', ['camera']),
    );
    reg('targetFolder', this.vec3(f, 'Alvo', c.target, 50, 'Ponto observado', ['camera']));
    this.action(f, '⤢ Enquadrar agora', 'Calcula a posição ideal para o trajeto atual', () =>
      this.actions.fitCameraNow(),
    );
    this.action(f, '▯ Modo retrato 9:16', 'Ajusta a saída para 1080×1920 e reenquadra', () =>
      this.actions.setPortrait(),
    );
    this.tip(
      f.add(this.ui, 'editorView').name('Vista livre (V)'),
      'Câmera de edição independente (não afeta a exportação)',
    ).onChange((v: boolean) => this.actions.setEditorView(v));
    this.resetButton(f, 'camera');
  }

  private buildLighting(): void {
    const f = this.folder(
      this.gui,
      '6. Iluminação',
      'Presets e luzes principal, preenchimento, recorte e ambiente',
    );
    const l = this.project.lighting;
    const custom = (): void => {
      if (l.preset !== 'custom') {
        l.preset = 'custom';
        this.lightingPresetController.updateDisplay();
      }
    };
    this.lightingPresetController = this.tip(
      f.add(l, 'preset', this.invert(LIGHTING_PRESET_LABELS)).name('Preset'),
      'Dark Neon, Clean Studio, Pastel, Metallic Gold, Wooden Warm',
    ).onChange((id: LightingPresetId) => {
      if (id !== 'custom') this.actions.applyLightingPreset(id);
    });
    this.num(
      f,
      l,
      'globalIntensity',
      LIGHTING_SPECS.globalIntensity,
      'Intensidade global',
      'Multiplicador de todas as luzes',
      ['lighting'],
      custom,
    );
    this.num(
      f,
      l,
      'exposure',
      LIGHTING_SPECS.exposure,
      'Exposição',
      'Exposição do tone mapping (0.5–3)',
      ['lighting'],
      custom,
    );
    this.select(
      f,
      l,
      'toneMapping',
      { Linear: 'linear', ACES: 'aces', AgX: 'agx', Neutral: 'neutral', Nenhum: 'none' },
      'Tone mapping',
      'Curva de tone mapping (padrão Linear)',
      ['lighting'],
      custom,
    );
    this.num(
      f,
      l,
      'environmentIntensity',
      LIGHTING_SPECS.environmentIntensity,
      'Reflexos (ambiente)',
      'Ambiente procedural para reflexos metálicos (0 = desligado)',
      ['lighting'],
      custom,
    );

    const amb = this.folder(f, 'Ambiente (Hemisphere)', 'Luz ambiente céu/terra');
    this.color(amb, l, 'skyColor', 'Cor do céu', 'Cor vinda de cima', ['lighting'], custom);
    this.color(amb, l, 'groundColor', 'Cor da terra', 'Cor vinda de baixo', ['lighting'], custom);
    this.num(
      amb,
      l,
      'ambientIntensity',
      LIGHTING_SPECS.ambientIntensity,
      'Intensidade',
      'Intensidade ambiente',
      ['lighting'],
      custom,
    );
    const main = this.folder(f, 'Principal', 'Luz direcional principal (com sombra)');
    this.color(main, l, 'mainColor', 'Cor', 'Cor da luz principal', ['lighting'], custom);
    this.num(
      main,
      l,
      'mainLightIntensity',
      LIGHTING_SPECS.mainLightIntensity,
      'Intensidade',
      'Intensidade da luz principal',
      ['lighting'],
      custom,
    );
    this.vec3(
      main,
      'Posição',
      l.mainPosition,
      50,
      'Direção/posição da luz principal',
      ['lighting'],
      custom,
    );
    const fill = this.folder(
      f,
      'Preenchimento (fill)',
      'Luz secundária que suaviza sombras (30–50% da principal)',
    );
    this.color(fill, l, 'fillColor', 'Cor', 'Cor do preenchimento', ['lighting'], custom);
    this.num(
      fill,
      l,
      'fillLightIntensity',
      LIGHTING_SPECS.fillLightIntensity,
      'Intensidade',
      'Intensidade do preenchimento',
      ['lighting'],
      custom,
    );
    this.vec3(
      fill,
      'Posição',
      l.fillPosition,
      50,
      'Direção do preenchimento',
      ['lighting'],
      custom,
    );
    const rim = this.folder(f, 'Recorte (rim)', 'Luz traseira que destaca contornos');
    this.color(rim, l, 'rimColor', 'Cor', 'Cor do recorte', ['lighting'], custom);
    this.num(
      rim,
      l,
      'rimLightIntensity',
      LIGHTING_SPECS.rimLightIntensity,
      'Intensidade',
      'Intensidade do recorte',
      ['lighting'],
      custom,
    );
    this.vec3(rim, 'Posição', l.rimPosition, 50, 'Direção do recorte', ['lighting'], custom);
    const shadows = this.folder(f, 'Sombras', 'Sombras da luz principal');
    this.bool(
      shadows,
      l,
      'shadowsEnabled',
      'Ativadas',
      'Liga/desliga sombras',
      ['lighting'],
      custom,
    );
    this.select(
      shadows,
      l,
      'shadowResolution',
      Object.fromEntries(SHADOW_RESOLUTIONS.map((r) => [String(r), r])),
      'Resolução',
      'Resolução do shadow map (512–2048)',
      ['lighting'],
      custom,
    );
    this.num(
      shadows,
      l,
      'shadowBias',
      LIGHTING_SPECS.shadowBias,
      'Bias',
      'Bias da sombra (−0.005 a 0.005)',
      ['lighting'],
      custom,
    );
    const pulse = this.folder(f, 'Pulsação', 'Variação periódica de intensidade');
    this.num(
      pulse,
      l,
      'pulseAmount',
      LIGHTING_SPECS.pulseAmount,
      'Amplitude',
      'Amplitude da pulsação (0 = desligada)',
      ['lighting'],
      custom,
    );
    this.num(
      pulse,
      l,
      'pulseCycles',
      LIGHTING_SPECS.pulseCycles,
      'Ciclos',
      'Pulsações por ciclo (inteiro)',
      ['lighting'],
      custom,
    );
    for (const sub of [amb, main, fill, rim, shadows, pulse]) sub.close();
    this.resetButton(f, 'lighting');
  }

  private buildBackground(): void {
    const f = this.folder(this.gui, '7. Fundo', 'Cor, gradiente, padrão, névoa e chão');
    const b = this.project.background;
    const refresh = (): void => this.refreshVisibility();
    this.select(
      f,
      b,
      'type',
      { 'Cor sólida': 'solid', Gradiente: 'gradient', Padrão: 'pattern' },
      'Tipo',
      'Tipo de fundo',
      ['background'],
      refresh,
    );
    this.color(f, b, 'colorMain', 'Cor principal', 'Cor sólida ou topo/centro do gradiente', [
      'background',
    ]);
    const secondary = this.color(
      f,
      b,
      'colorSecondary',
      'Cor secundária',
      'Base/borda do gradiente',
      ['background'],
    );
    const mode = this.select(
      f,
      b,
      'gradientMode',
      { Vertical: 'vertical', Radial: 'radial' },
      'Gradiente',
      'Direção do gradiente',
      ['background'],
    );
    const pattern = this.select(
      f,
      b,
      'pattern',
      { Grade: 'grid', Pontos: 'dots', Nenhum: 'none' },
      'Padrão',
      'Padrão desenhado sobre o fundo',
      ['background'],
    );
    const patternColor = this.color(
      f,
      b,
      'patternColor',
      'Cor do padrão',
      'Cor das linhas/pontos',
      ['background'],
    );
    const patternScale = this.num(
      f,
      b,
      'patternScale',
      BACKGROUND_SPECS.patternScale,
      'Escala do padrão',
      'Tamanho das células',
      ['background'],
    );
    this.bgGradientControllers = [secondary, mode];
    this.bgPatternControllers = [pattern, patternColor, patternScale];

    const fog = this.folder(f, 'Névoa', 'Névoa linear ou exponencial');
    this.bool(fog, b, 'fogEnabled', 'Ativada', 'Liga/desliga a névoa', ['background']);
    this.select(
      fog,
      b,
      'fogType',
      { Linear: 'linear', Exponencial: 'exponential' },
      'Tipo',
      'Linear (near/far) ou exponencial (densidade)',
      ['background'],
      refresh,
    );
    this.bool(
      fog,
      b,
      'fogMatchBackground',
      'Igual ao fundo',
      'Usa a cor do fundo na névoa',
      ['background'],
      refresh,
    );
    this.fogColor = this.color(fog, b, 'fogColor', 'Cor', 'Cor da névoa', ['background']);
    this.fogLinear = [
      this.num(fog, b, 'fogNear', BACKGROUND_SPECS.fogNear, 'Near', 'Início da névoa', [
        'background',
      ]),
      this.num(fog, b, 'fogFar', BACKGROUND_SPECS.fogFar, 'Far', 'Névoa total', ['background']),
    ];
    this.fogExp = [
      this.num(
        fog,
        b,
        'fogDensity',
        BACKGROUND_SPECS.fogDensity,
        'Densidade',
        'Densidade exponencial',
        ['background'],
      ),
    ];

    const ground = this.folder(f, 'Chão', 'Plano de chão opcional');
    this.bool(ground, b, 'groundEnabled', 'Ativado', 'Mostra o chão', ['background']);
    this.num(
      ground,
      b,
      'groundHeight',
      BACKGROUND_SPECS.groundHeight,
      'Altura (Y)',
      'Posição vertical do chão',
      ['background'],
    );
    this.color(ground, b, 'groundColor', 'Cor', 'Cor do chão', ['background']);
    this.num(
      ground,
      b,
      'groundOpacity',
      BACKGROUND_SPECS.groundOpacity,
      'Opacidade',
      'Opacidade do chão',
      ['background'],
    );
    this.num(ground, b, 'groundSize', BACKGROUND_SPECS.groundSize, 'Tamanho', 'Lado do plano', [
      'background',
    ]);
    this.num(
      ground,
      b,
      'groundRoughness',
      BACKGROUND_SPECS.groundRoughness,
      'Roughness',
      'Rugosidade (reflexividade)',
      ['background'],
    );
    this.num(
      ground,
      b,
      'groundMetalness',
      BACKGROUND_SPECS.groundMetalness,
      'Metalness',
      'Reflexividade metálica',
      ['background'],
    );
    fog.close();
    ground.close();
    this.resetButton(f, 'background');
  }

  private buildLoop(): void {
    const f = this.folder(this.gui, '8. Loop', 'Duração, FPS e ciclos do loop');
    const l = this.project.loop;
    this.num(
      f,
      l,
      'durationSeconds',
      LOOP_SPECS.durationSeconds,
      'Duração (s)',
      'Duração do loop (1–300 s)',
      ['loop'],
    );
    this.select(
      f,
      l,
      'fps',
      { '30': 30, '60': 60 },
      'FPS do preview',
      'Grade de frames do preview (igual ao export = resultado idêntico)',
      ['loop'],
    );
    this.num(
      f,
      l,
      'cycleCount',
      LOOP_SPECS.cycleCount,
      'Cycle count',
      'Repetições inteiras da coreografia dentro do loop',
      ['loop'],
    );
    this.tip(
      f
        .add(this.ui, 'speed', MIN_PREVIEW_SPEED, MAX_PREVIEW_SPEED, 0.25)
        .name('Velocidade do preview'),
      'Velocidade só do preview (0.25× a 2×)',
    ).onChange((v: number) => this.actions.setPreviewSpeed(v));
    this.tip(
      f.add(this.ui, 'playing').name('Reproduzindo').listen(),
      'Play/Pause (Espaço)',
    ).onChange((v: boolean) => this.actions.setPlaying(v));
    this.tip(
      f.add(this.ui, 'time', 0, 0.999, 0.001).name('Tempo (0–1)').listen(),
      'Posição no loop; arraste para navegar (pausa o preview)',
    ).onChange((v: number) => this.actions.seek(v));
    this.resetButton(f, 'loop');
  }

  private buildExport(progressElement: HTMLElement): void {
    const f = this.folder(this.gui, '9. Exportação', 'Resolução, duração, arquivo e exportação');
    const o = this.project.output;
    const presets = Object.fromEntries(RESOLUTION_PRESETS.map((r) => [r.label, r.id]));
    this.tip(
      f.add(o, 'resolutionPreset', presets).name('Resolução'),
      'Presets 9:16, 16:9, 1:1 ou custom (máx. 4K)',
    ).onChange((id: ResolutionPresetId) => this.actions.applyResolutionPreset(id));
    this.widthController = this.num(
      f,
      o,
      'width',
      OUTPUT_SPECS.width,
      'Largura',
      'Largura em pixels (par, máx. 3840)',
      ['output'],
    );
    this.heightController = this.num(
      f,
      o,
      'height',
      OUTPUT_SPECS.height,
      'Altura',
      'Altura em pixels (par, máx. 3840)',
      ['output'],
    );
    this.num(
      f,
      o,
      'durationSeconds',
      OUTPUT_SPECS.durationSeconds,
      'Duração (s)',
      'Duração do vídeo (1–300 s)',
      ['output'],
    );
    this.select(f, o, 'fps', { '30': 30, '60': 60 }, 'FPS', 'Taxa de quadros do vídeo', ['output']);
    this.bool(
      f,
      o,
      'autoLoop',
      'Auto loop',
      'Ajusta a duração para múltiplo inteiro do loop (sem emenda)',
      ['output'],
    );
    this.num(
      f,
      o,
      'bitrateMbps',
      OUTPUT_SPECS.bitrateMbps,
      'Bitrate (Mbps)',
      'Qualidade do vídeo (2–15 Mbps)',
      ['output'],
    );
    this.select(
      f,
      o,
      'codec',
      { 'VP8 (compatível)': 'vp8', 'VP9 (menor arquivo)': 'vp9' },
      'Codec',
      'VP8 padrão; VP9 se suportado',
      ['output'],
    );
    this.select(
      f,
      o,
      'encoder',
      { 'MediaRecorder (padrão)': 'mediaRecorder', 'WebCodecs (frame-exato)': 'webCodecs' },
      'Encoder',
      'MediaRecorder grava em tempo real; WebCodecs usa timestamps exatos e independe da GPU',
      ['output'],
    );
    this.bindChange(
      this.tip(
        f.add(o, 'fileName').name('Nome do arquivo'),
        'Vazio = infinite-marble-{preset}-{seed}-{w}x{h}',
      ),
      [],
    );
    this.tip(
      f.add(this.ui, 'safeArea').name('Área segura'),
      'Mostra margens de 20% para textos (não aparece na exportação)',
    ).onChange((v: boolean) => this.actions.setSafeArea(v));
    this.tip(
      f.add(this.ui, 'pixelRatio', { '1×': 1, '1.5×': 1.5, '2×': 2 }).name('Pixel ratio (preview)'),
      'Limite de devicePixelRatio do preview',
    ).onChange((v: number) => this.actions.setPixelRatio(v));
    this.tip(
      f.add(this.ui, 'previewExportRes').name('Preview na resolução final'),
      'Renderiza o preview na resolução de exportação',
    ).onChange((v: boolean) => this.actions.setPreviewAtExportResolution(v));
    f.$children.append(this.exportInfo);
    this.action(f, '● Exportar vídeo (Ctrl+E)', 'Grava o loop em WebM (frame a frame)', () =>
      this.actions.exportVideo(),
    );
    this.action(f, '▣ Capturar PNG', 'Captura o frame atual na resolução final', () =>
      this.actions.capturePng(),
    );
    this.action(
      f,
      '≡ Verificar determinismo',
      'Compara pixels do preview e do export (tolerância 2 RGBA)',
      () => this.actions.verifyDeterminism(),
    );
    f.$children.append(progressElement);
    const history = this.folder(f, 'Histórico', 'Últimas 10 exportações');
    history.$children.append(this.historyPanel.element);
    history.close();
    this.resetButton(f, 'output');
  }

  private buildPresets(): void {
    const f = this.folder(this.gui, '10. Presets', 'Salvar, carregar, importar e exportar presets');
    this.tip(f.add(this.ui, 'presetName').name('Nome do preset'), 'Nome usado ao salvar');
    this.action(f, '💾 Salvar preset (Ctrl+S)', 'Salva no navegador (localStorage)', () =>
      this.actions.savePreset(this.ui.presetName || this.project.name),
    );
    this.presetSelect = this.tip(
      f.add(this.ui, 'presetKey', this.actions.getPresetOptions()).name('Presets'),
      'Built-in e salvos',
    );
    this.action(f, '📂 Carregar', 'Carrega o preset selecionado', () =>
      this.actions.loadPreset(this.ui.presetKey),
    );
    this.action(f, '🗑 Excluir', 'Exclui o preset salvo selecionado', () =>
      this.actions.deletePreset(this.ui.presetKey),
    );
    this.action(f, '⬇ Exportar JSON', 'Baixa o projeto atual como .json', () =>
      this.actions.exportJson(),
    );
    this.action(f, '⬆ Importar JSON', 'Carrega um arquivo .json (ou arraste para a janela)', () =>
      this.actions.importJson(),
    );
    this.action(f, '↺ Restaurar padrão', 'Volta ao projeto padrão (pode desfazer)', () =>
      this.actions.restoreDefaults(),
    );
  }

  // ---------------------------------------------------------------- atualização

  private writeCustomColors(): void {
    const colors: number[] = [];
    for (let i = 0; i < this.ui.customCount; i++) colors.push(this.colorProxy[`c${i}`] ?? 0xffffff);
    this.project.marbles.customColors = colors;
    this.project.marbles.palette = 'custom';
    this.refreshVisibility();
  }

  private readCustomColors(): void {
    const colors = this.project.marbles.customColors;
    this.ui.customCount = Math.min(MAX_CUSTOM_COLORS, Math.max(1, colors.length));
    for (let i = 0; i < MAX_CUSTOM_COLORS; i++) {
      this.colorProxy[`c${i}`] = colors[i] ?? this.colorProxy[`c${i}`] ?? 0xffffff;
    }
  }

  refreshPresetOptions(selectedKey?: string): void {
    const options = this.actions.getPresetOptions();
    if (selectedKey !== undefined) this.ui.presetKey = selectedKey;
    else if (!Object.values(options).includes(this.ui.presetKey))
      this.ui.presetKey = Object.values(options)[0] ?? '';
    this.presetSelect = this.tip(
      this.presetSelect.options(options).name('Presets'),
      'Built-in e salvos',
    );
  }

  /** Atualiza todos os controles após mudanças externas (preset, undo, variação). */
  refresh(): void {
    this.readCustomColors();
    this.ui.editorView = this.runtime.editorView;
    this.ui.safeArea = this.runtime.showSafeArea;
    this.ui.pixelRatio = this.runtime.maxPixelRatio;
    this.ui.previewExportRes = this.runtime.previewAtExportResolution;
    this.ui.speed = this.runtime.previewSpeed;
    for (const controller of this.gui.controllersRecursive()) controller.updateDisplay();
    this.refreshVisibility();
  }

  refreshVisibility(): void {
    const { track, marbles, camera, background, output } = this.project;
    this.trackControllers.radius.show(track.style === 'tube');
    this.trackControllers.railDistance.show(track.style === 'dualRail');
    this.trackControllers.railRadius.show(track.style === 'dualRail');
    const custom = marbles.palette === 'custom';
    this.customCountController.show(custom);
    this.customColorControllers.forEach((c, i) => c.show(custom && i < this.ui.customCount));
    this.spinCyclesController.enable(!marbles.spinAuto);
    for (const [key, controller] of this.cameraControllers) {
      const modes = CAMERA_VISIBILITY[key as keyof typeof CAMERA_VISIBILITY];
      let visible = !modes || modes.includes(camera.mode);
      if (key === 'distance' && camera.autoFrame && camera.mode !== 'follow') visible = false;
      controller.show(visible);
    }
    this.bgGradientControllers.forEach((c) => c.show(background.type !== 'solid'));
    this.bgPatternControllers.forEach((c) => c.show(background.type === 'pattern'));
    this.fogLinear.forEach((c) => c.show(background.fogType === 'linear'));
    this.fogExp.forEach((c) => c.show(background.fogType === 'exponential'));
    this.fogColor.show(!background.fogMatchBackground);
    const customResolution = output.resolutionPreset === 'custom';
    this.widthController.enable(customResolution);
    this.heightController.enable(customResolution);
  }

  /** Valores exibidos na seção Projeto e no tempo do loop (chamado ~4×/s e por frame). */
  setLiveInfo(info: { fps: number; normalizedTime: number; playing: boolean }): void {
    this.ui.fps = info.fps > 0 ? info.fps.toFixed(0) : '–';
    this.ui.marbles = String(this.project.marbles.count);
    this.ui.loop = `${this.project.loop.durationSeconds}s @ ${this.project.loop.fps} fps`;
    this.ui.time = Number(info.normalizedTime.toFixed(3));
    this.ui.playing = info.playing;
  }

  setPathStatus(result: PathValidationResult, pointCount: number): void {
    const lines: HTMLElement[] = [];
    const ok = result.valid && result.closed;
    lines.push(
      el('div', { className: ok ? 'status-ok' : 'status-bad' }, [
        `${ok ? '✓' : '⚠'} Curva ${result.closed ? 'fechada' : 'aberta'} e ${result.valid ? 'válida' : 'inválida'} (${pointCount} pontos)`,
      ]),
    );
    for (const error of result.errors)
      lines.push(el('div', { className: 'status-bad' }, [`• ${error}`]));
    for (const warning of result.warnings.slice(0, 4))
      lines.push(el('div', { className: 'status-warn' }, [`• ${warning}`]));
    if (result.warnings.length > 4) {
      lines.push(
        el('div', { className: 'status-warn' }, [`• +${result.warnings.length - 4} avisos`]),
      );
    }
    this.pathStatus.replaceChildren(...lines);
  }

  setVariationReport(text: string): void {
    this.variationReport.textContent = text;
    this.variationReport.hidden = text.length === 0;
  }

  setExportInfo(text: string): void {
    this.exportInfo.textContent = text;
  }

  setVisible(visible: boolean): void {
    if (visible) this.gui.show();
    else this.gui.hide();
  }
}
