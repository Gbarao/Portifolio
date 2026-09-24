import { computeFitDistance } from '../camera/CameraRig';
import { CAMERA_MODE_DEFAULTS } from '../camera/CameraFactory';
import { debounce, type Debounced } from '../core/Debounce';
import { History } from '../core/History';
import { LoopClock, computeTotalFrames } from '../core/LoopClock';
import { PerformanceMonitor, getPerformanceRecommendations } from '../core/PerformanceMonitor';
import { createRandomSeed } from '../core/SeedSource';
import { normalizeSeed } from '../core/SeededRandom';
import type { CaptureHost } from '../export/CaptureHost';
import { downloadBlob, downloadText } from '../export/DownloadUtils';
import {
  ExportHistory,
  type ExportHistoryEntry,
  type ExportHistoryKind,
} from '../export/ExportHistory';
import {
  estimateFileSizeBytes,
  resolveExportPlan,
  validateExport,
  type ExportKind,
} from '../export/ExportValidator';
import { buildExportFileName } from '../export/FileNaming';
import { ImageExporter } from '../export/ImageExporter';
import {
  ExportCancelledError,
  VideoExporter,
  isVideoRecordingSupported,
  isWebCodecsSupported,
  webCodecsConfig,
} from '../export/VideoExporter';
import { PathEditor, type Axis } from '../path/PathEditor';
import { autoFitPath, createPresetPoints } from '../path/PathFactory';
import { validatePathPoints, type PathValidationResult } from '../path/PathValidator';
import {
  BUILT_IN_PRESETS,
  createDefaultProject,
  createLightingPreset,
  findBuiltInPreset,
} from '../presets/DefaultPresets';
import {
  RESOLUTION_PRESETS,
  type CameraMode,
  type LightingPresetId,
  type PathPresetId,
  type ResolutionPresetId,
  type ScenePreset,
  type SectionKey,
  type Vec3Like,
} from '../presets/PresetSchema';
import { PresetStore, getBrowserStorage } from '../presets/PresetStore';
import { deserializePreset, serializePreset } from '../presets/PresetValidator';
import {
  ALL_VARIATION_CATEGORIES,
  APPEARANCE_CATEGORIES,
  PATH_PRESET_BANK,
  createVariation,
  formatVariationReport,
  type VariationOptions,
} from '../presets/VariationGenerator';
import { RendererManager } from '../scene/RendererManager';
import { SceneManager, type DirtySection } from '../scene/SceneManager';
import { ControlPanel } from '../ui/ControlPanel';
import { formatBytes, requireElement } from '../ui/dom';
import { ExportProgress } from '../ui/ExportProgress';
import { installKeyboardShortcuts } from '../ui/KeyboardShortcuts';
import { Notifier } from '../ui/Notifier';
import { SafeAreaOverlay } from '../ui/SafeAreaOverlay';
import { ShortcutsDialog } from '../ui/ShortcutsDialog';
import { StatusPanel } from '../ui/StatusPanel';
import { TopBar } from '../ui/TopBar';
import { AppState, assignDeep } from './AppState';
import { ErrorHandler, type NotifyAction, type NotifyLevel } from './ErrorHandler';
import { EventBus } from './EventBus';

export interface AppEvents {
  projectChanged: { sections: DirtySection[]; commit: boolean };
  projectReplaced: { message: string };
  exportStateChanged: { exporting: boolean };
}

export interface DeterminismReport {
  frameIndex: number;
  previewTime: number;
  exportTime: number;
  timesIdentical: boolean;
  maxChannelDiff: number;
  repeatMaxChannelDiff: number;
  differingPixels: number;
  passed: boolean;
}

const GEOMETRY_SECTIONS: ReadonlySet<DirtySection> = new Set(['path', 'track']);

/** Orquestra estado, cena, relógio, interface, persistência e exportação. */
export class App implements CaptureHost {
  readonly state: AppState;
  readonly bus = new EventBus<AppEvents>();
  readonly canvas: HTMLCanvasElement;
  readonly clock: LoopClock;
  readonly sceneManager: SceneManager;
  private readonly notifier: Notifier;
  private readonly errors: ErrorHandler;
  private readonly rendererManager: RendererManager;
  private readonly perf = new PerformanceMonitor(60);
  private readonly presetStore: PresetStore;
  private readonly exportHistory: ExportHistory;
  private readonly history: History<string>;
  private readonly panel: ControlPanel;
  private readonly statusPanel: StatusPanel;
  private readonly topBar: TopBar;
  private readonly shortcutsDialog: ShortcutsDialog;
  private readonly exportProgress: ExportProgress;
  private readonly safeArea: SafeAreaOverlay;
  private readonly videoExporter: VideoExporter;
  private readonly imageExporter: ImageExporter;
  private readonly sidebar: HTMLElement;
  private readonly fileInput: HTMLInputElement;
  private readonly sessionBlobs = new Map<string, Blob>();
  private readonly pendingImmediate = new Set<DirtySection>();
  private readonly pendingGeometry = new Set<DirtySection>();
  private readonly geometryDebounce: Debounced<[]>;
  private readonly autosave: Debounced<[]>;
  private pathValidation: PathValidationResult;
  private lastStatusUpdate = 0;
  private recordingStartedAt: number | null = null;
  private exportAbort: AbortController | null = null;
  private capturing = false;
  private running = false;

  constructor() {
    this.notifier = new Notifier(requireElement('toasts'));
    this.errors = new ErrorHandler((message, level, action) => this.notify(message, level, action));
    this.errors.install();

    const storage = getBrowserStorage();
    this.presetStore = new PresetStore(storage);
    this.exportHistory = new ExportHistory(storage);

    const draft = this.presetStore.loadDraft();
    let initial = createDefaultProject();
    if (draft?.ok) {
      initial = draft.preset;
    } else if (draft && !draft.ok) {
      this.notify(
        `O rascunho salvo é inválido e foi ignorado: ${draft.errors[0] ?? ''}`,
        'warning',
        {
          label: 'Apagar rascunho',
          run: () => this.presetStore.clearDraft(),
        },
      );
    }
    this.state = AppState.initialize(initial);
    const project = this.state.project;

    this.sidebar = requireElement('sidebar');
    this.rendererManager = new RendererManager(requireElement('viewport'));
    this.canvas = this.rendererManager.canvas;
    this.clock = new LoopClock({
      durationSeconds: project.loop.durationSeconds,
      fps: project.loop.fps,
    });
    this.sceneManager = new SceneManager(this.rendererManager, project);
    this.history = new History(this.state.snapshot(), 50);
    this.videoExporter = new VideoExporter(this);
    this.imageExporter = new ImageExporter(this);
    this.geometryDebounce = debounce(() => this.flushGeometry(), 100);
    this.autosave = debounce(() => this.saveDraft(), 500);
    this.pathValidation = validatePathPoints(project.path.points, project.path.closed);

    this.topBar = new TopBar(requireElement('topbar'), {
      togglePlay: () => this.togglePlay(),
      restart: () => this.clock.reset(),
      randomizeAll: () =>
        this.randomize({ categories: ALL_VARIATION_CATEGORIES }, 'Randomizar tudo'),
      randomizePath: () =>
        this.randomize({ categories: ['path'], forceRandomPath: true }, 'Trajeto randomizado'),
      randomizeAppearance: () =>
        this.randomize({ categories: APPEARANCE_CATEGORIES }, 'Aparência randomizada'),
      newVariation: () => this.randomize({}, 'Nova variação'),
      undo: () => this.undo(),
      redo: () => this.redo(),
      toggleHelpers: () => this.setHelpersVisible(!this.state.runtime.helpersVisible),
      toggleGui: () => this.setGuiVisible(!this.state.runtime.guiVisible),
      toggleEditorView: () => this.setEditorView(!this.state.runtime.editorView),
      showShortcuts: () => this.shortcutsDialog.toggle(),
    });
    this.statusPanel = new StatusPanel(requireElement('status-panel'));
    this.shortcutsDialog = new ShortcutsDialog(
      requireElement<HTMLDialogElement>('shortcuts-dialog'),
    );
    this.exportProgress = new ExportProgress(requireElement('export-overlay'), {
      cancel: () => this.exportAbort?.abort(),
      rerecord: () => {
        this.exportProgress.hide();
        void this.exportVideo();
      },
    });
    this.safeArea = new SafeAreaOverlay(requireElement('safe-area'), this.canvas);
    this.rendererManager.onLayout = () => this.safeArea.sync();

    this.panel = new ControlPanel(
      this.sidebar,
      project,
      this.state.runtime,
      {
        onChange: (sections, commit) => this.onSettingsChanged(sections, commit),
        newVariation: () => this.randomize({}, 'Nova variação'),
        applyPathPreset: (id) => this.applyPathPreset(id),
        addPoint: () =>
          this.editPath((points, sel) => PathEditor.addPoint(points, sel, project.path.closed)),
        duplicatePoint: () => this.duplicateSelectedPoint(),
        removeSelectedPoint: () => this.removeSelectedPoint(),
        randomizePath: () =>
          this.randomize({ categories: ['path'], forceRandomPath: true }, 'Trajeto randomizado'),
        autoFitPath: () => this.autoFit(),
        pointTable: {
          select: (index) => this.sceneManager.handles.select(index),
          remove: (index) => this.editPath((points) => PathEditor.removePoint(points, index)),
          setCoordinate: (index, axis, value) => this.setCoordinate(index, axis, value),
        },
        applyCameraMode: (mode) => this.applyCameraMode(mode),
        fitCameraNow: () => this.fitCameraNow(),
        setPortrait: () => this.setPortrait(),
        setEditorView: (enabled) => this.setEditorView(enabled),
        applyLightingPreset: (id) => this.applyLightingPreset(id),
        setPlaying: (playing) => this.setPlaying(playing),
        setPreviewSpeed: (speed) => {
          this.clock.setSpeed(speed);
          this.state.runtime.previewSpeed = this.clock.previewSpeed;
        },
        seek: (t) => {
          this.clock.pause();
          this.clock.seekNormalized(t);
          this.updateTopBar();
        },
        applyResolutionPreset: (id) => this.applyResolutionPreset(id),
        exportVideo: () => void this.exportVideo(),
        capturePng: () => void this.capturePng(),
        verifyDeterminism: () => void this.verifyDeterminism(),
        setSafeArea: (visible) => this.setSafeArea(visible),
        setPixelRatio: (ratio) => {
          this.state.runtime.maxPixelRatio = ratio;
          this.rendererManager.maxPixelRatio = ratio;
          this.rendererManager.layout();
        },
        setPreviewAtExportResolution: (enabled) => {
          this.state.runtime.previewAtExportResolution = enabled;
          this.rendererManager.previewAtExportResolution = enabled;
          this.rendererManager.layout();
        },
        history: {
          redownload: (entry) => void this.redownload(entry),
          remove: (entry) => {
            this.sessionBlobs.delete(entry.id);
            this.panel.historyPanel.render(this.exportHistory.remove(entry.id));
          },
        },
        savePreset: (name) => this.savePreset(name),
        loadPreset: (key) => this.loadPresetByKey(key),
        deletePreset: (key) => this.deletePreset(key),
        exportJson: () => this.exportJson(),
        importJson: () => this.fileInput.click(),
        restoreDefaults: () =>
          this.loadProject(createDefaultProject(), 'Projeto padrão restaurado.'),
        resetSection: (section) => this.resetSection(section),
        getPresetOptions: () => this.getPresetOptions(),
      },
      this.exportProgress.inline,
    );

    this.fileInput = document.createElement('input');
    this.fileInput.type = 'file';
    this.fileInput.accept = '.json,application/json';
    this.fileInput.hidden = true;
    this.fileInput.addEventListener('change', () => {
      const file = this.fileInput.files?.[0];
      if (file) void this.importFile(file);
      this.fileInput.value = '';
    });
    document.body.append(this.fileInput);

    this.wireScene();
    this.wireGlobalEvents();
    this.updatePathUi();
    this.updateExportInfo();
    this.updateTopBar();
    this.panel.historyPanel.render(this.exportHistory.list());
    this.panel.setVariationReport('');
  }

  // ------------------------------------------------------------------ setup

  private notify(message: string, level: NotifyLevel = 'info', action?: NotifyAction): void {
    this.notifier.show(message, level, action);
  }

  private wireScene(): void {
    const handles = this.sceneManager.handles;
    handles.onSelect = (index) => {
      this.state.runtime.selectedPoint = index;
      this.panel.pointTable.render(this.state.project.path.points, index);
    };
    handles.onPointMoved = (index, position) => {
      const path = this.state.project.path;
      path.points = PathEditor.movePoint(path.points, index, position).points;
      path.preset = 'custom';
      this.onSettingsChanged(['path'], false);
      this.panel.pointTable.render(path.points, index);
    };
    handles.onDragEnd = () => {
      this.panel.refresh();
      this.commitHistory();
    };
    this.sceneManager.onFixedCameraEdited = (position, target) => {
      const camera = this.state.project.camera;
      Object.assign(camera.position, round3(position));
      Object.assign(camera.target, round3(target));
      camera.autoFrame = false;
      this.onSettingsChanged(['camera'], false);
    };
    this.sceneManager.onFixedCameraEditEnd = () => {
      this.panel.refresh();
      this.commitHistory();
    };
    this.canvas.addEventListener('webglcontextlost', (event) => {
      event.preventDefault();
      this.notify(
        'Contexto WebGL perdido (GPU reiniciada ou sem memória). Recarregue a página.',
        'error',
      );
    });
  }

  private wireGlobalEvents(): void {
    installKeyboardShortcuts(
      {
        togglePlay: () => this.togglePlay(),
        restart: () => this.clock.reset(),
        randomizeAll: () =>
          this.randomize({ categories: ALL_VARIATION_CATEGORIES }, 'Randomizar tudo'),
        randomizePath: () =>
          this.randomize({ categories: ['path'], forceRandomPath: true }, 'Trajeto randomizado'),
        randomizeAppearance: () =>
          this.randomize({ categories: APPEARANCE_CATEGORIES }, 'Aparência randomizada'),
        newVariation: () => this.randomize({}, 'Nova variação'),
        undo: () => this.undo(),
        redo: () => this.redo(),
        savePreset: () => this.savePreset(this.state.project.name),
        exportVideo: () => void this.exportVideo(),
        toggleHelpers: () => this.setHelpersVisible(!this.state.runtime.helpersVisible),
        toggleGui: () => this.setGuiVisible(!this.state.runtime.guiVisible),
        toggleEditorView: () => this.setEditorView(!this.state.runtime.editorView),
        showShortcuts: () => this.shortcutsDialog.toggle(),
        deletePoint: () => this.removeSelectedPoint(),
        duplicatePoint: () => this.duplicateSelectedPoint(),
        escape: () => {
          if (this.shortcutsDialog.isOpen) this.shortcutsDialog.close();
          else if (!this.state.runtime.exporting) this.sceneManager.handles.select(null);
        },
      },
      () => this.state.runtime.exporting,
    );

    window.addEventListener('dragover', (event) => {
      event.preventDefault();
      document.body.classList.add('is-dragging');
    });
    window.addEventListener('dragleave', (event) => {
      if (event.relatedTarget === null) document.body.classList.remove('is-dragging');
    });
    window.addEventListener('drop', (event) => {
      event.preventDefault();
      document.body.classList.remove('is-dragging');
      const file = event.dataTransfer?.files[0];
      if (!file) return;
      if (!/\.json$/i.test(file.name) && file.type !== 'application/json') {
        this.notify(`"${file.name}" não é um arquivo JSON de preset.`, 'error');
        return;
      }
      void this.importFile(file);
    });
    window.addEventListener('beforeunload', (event) => {
      if (this.state.runtime.exporting || this.state.runtime.dirtySinceSave) {
        this.saveDraft();
        event.preventDefault();
        event.returnValue = '';
      }
    });
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    const frame = (now: number): void => {
      if (!this.running) return;
      requestAnimationFrame(frame);
      if (this.state.runtime.exporting || this.capturing) return;
      this.flushImmediate();
      const t = this.clock.getNormalizedTime();
      this.sceneManager.renderAt(t);
      this.perf.recordFrame(now);
      this.panel.setLiveInfo({
        fps: this.perf.getSnapshot().fps,
        normalizedTime: t,
        playing: this.clock.isPlaying,
      });
      if (now - this.lastStatusUpdate > 250) {
        this.lastStatusUpdate = now;
        this.updateStatus();
      }
    };
    requestAnimationFrame(frame);
  }

  stop(): void {
    this.running = false;
  }

  // ------------------------------------------------------------------ mudanças

  private onSettingsChanged(sections: DirtySection[], commit: boolean): void {
    if (this.state.runtime.exporting) return;
    const project = this.state.project;
    for (const section of sections) {
      if (GEOMETRY_SECTIONS.has(section)) this.pendingGeometry.add(section);
      else this.pendingImmediate.add(section);
    }
    if (this.pendingGeometry.size > 0) this.geometryDebounce();
    if (sections.includes('seed')) project.seed = normalizeSeed(project.seed);
    if (sections.includes('loop')) {
      this.clock.configure(project.loop.durationSeconds, project.loop.fps);
    }
    if (sections.includes('output') || sections.includes('loop')) this.updateExportInfo();
    if (sections.includes('path')) this.updatePathUi();
    this.state.runtime.dirtySinceSave = true;
    this.autosave();
    if (commit) this.commitHistory();
    this.bus.emit('projectChanged', { sections, commit });
  }

  private flushImmediate(): void {
    if (this.pendingImmediate.size === 0) return;
    const sections = new Set(this.pendingImmediate);
    this.pendingImmediate.clear();
    this.sceneManager.applyChanges(this.state.project, sections);
    if (sections.has('camera') || sections.has('output')) this.panel.refreshVisibility();
  }

  private flushGeometry(): void {
    const sections = new Set([...this.pendingGeometry, ...this.pendingImmediate]);
    this.pendingGeometry.clear();
    this.pendingImmediate.clear();
    if (sections.size > 0) this.sceneManager.applyChanges(this.state.project, sections);
    this.updatePathUi();
  }

  /** Aplica imediatamente qualquer alteração pendente (antes de exportar, por exemplo). */
  flushPending(): void {
    this.geometryDebounce.cancel();
    this.flushGeometry();
  }

  /** Reaplica o projeto inteiro (após undo/redo, carregar preset, variação). */
  private applyAll(): void {
    this.geometryDebounce.cancel();
    this.pendingGeometry.clear();
    this.pendingImmediate.clear();
    const project = this.state.project;
    this.clock.configure(project.loop.durationSeconds, project.loop.fps);
    this.sceneManager.handles.select(null, false);
    this.state.runtime.selectedPoint = null;
    this.sceneManager.applyChanges(project, new Set<DirtySection>(['all']));
    this.panel.refresh();
    this.updatePathUi();
    this.updateExportInfo();
    this.state.runtime.dirtySinceSave = true;
    this.autosave();
  }

  private commitHistory(): void {
    if (this.history.push(this.state.snapshot())) this.updateTopBar();
  }

  private saveDraft(): void {
    try {
      this.presetStore.saveDraft(this.state.project);
    } catch (error) {
      this.errors.report(error, 'Falha ao salvar rascunho');
    }
  }

  undo(): void {
    const snapshot = this.history.undo();
    if (snapshot === null) {
      this.notify('Nada para desfazer.', 'info');
      return;
    }
    this.state.replaceProject(JSON.parse(snapshot) as ScenePreset);
    this.applyAll();
    this.updateTopBar();
  }

  redo(): void {
    const snapshot = this.history.redo();
    if (snapshot === null) {
      this.notify('Nada para refazer.', 'info');
      return;
    }
    this.state.replaceProject(JSON.parse(snapshot) as ScenePreset);
    this.applyAll();
    this.updateTopBar();
  }

  /** Substitui o projeto (preset, importação, variação) com registro no histórico. */
  loadProject(preset: ScenePreset, message: string, level: NotifyLevel = 'success'): void {
    this.state.replaceProject(preset);
    this.applyAll();
    this.commitHistory();
    if (message) this.notify(message, level);
  }

  // ------------------------------------------------------------------ trajeto

  private updatePathUi(): void {
    const path = this.state.project.path;
    this.pathValidation = validatePathPoints(path.points, path.closed);
    this.panel.setPathStatus(this.pathValidation, path.points.length);
    this.panel.pointTable.render(path.points, this.state.runtime.selectedPoint);
  }

  private editPath(
    operation: (
      points: Vec3Like[],
      selected: number | null,
    ) => { points: Vec3Like[]; selectedIndex: number | null },
  ): void {
    const path = this.state.project.path;
    try {
      const result = operation(path.points, this.state.runtime.selectedPoint);
      path.points = result.points;
      path.preset = 'custom';
      this.state.runtime.selectedPoint = result.selectedIndex;
      this.onSettingsChanged(['path'], true);
      this.flushPending();
      this.sceneManager.handles.select(result.selectedIndex);
      this.panel.refresh();
    } catch (error) {
      this.notify(error instanceof Error ? error.message : String(error), 'warning');
    }
  }

  private duplicateSelectedPoint(): void {
    const selected = this.state.runtime.selectedPoint;
    if (selected === null) {
      this.notify('Selecione um ponto (clique em um handle ou use ◎ na tabela).', 'info');
      return;
    }
    this.editPath((points) =>
      PathEditor.duplicatePoint(points, selected, this.state.project.path.closed),
    );
  }

  private removeSelectedPoint(): void {
    const selected = this.state.runtime.selectedPoint;
    if (selected === null) {
      this.notify('Selecione um ponto para remover.', 'info');
      return;
    }
    this.editPath((points) => PathEditor.removePoint(points, selected));
  }

  private setCoordinate(index: number, axis: Axis, value: number): void {
    this.editPath((points) => PathEditor.setCoordinate(points, index, axis, value));
  }

  private applyPathPreset(id: PathPresetId): void {
    if (id === 'custom') {
      this.randomize({ categories: ['path'], forceRandomPath: true }, 'Trajeto randomizado');
      return;
    }
    const project = this.state.project;
    project.path.points = createPresetPoints(id);
    project.path.preset = id;
    project.path.closed = true;
    project.track.bankAngle = PATH_PRESET_BANK[id] ?? 0;
    this.sceneManager.handles.select(null, false);
    this.state.runtime.selectedPoint = null;
    this.onSettingsChanged(['path', 'track'], true);
    this.panel.refresh();
  }

  private autoFit(): void {
    const path = this.state.project.path;
    path.points = autoFitPath(path.points, {
      closed: path.closed,
      curveType: path.curveType,
      tension: path.tension,
    });
    this.onSettingsChanged(['path'], true);
    this.panel.refresh();
    this.notify('Trajeto centralizado e ajustado ao raio 5.', 'success');
  }

  // ------------------------------------------------------------------ variações

  private randomize(options: VariationOptions, title: string): void {
    if (this.state.runtime.exporting) return;
    const seed = createRandomSeed();
    const result = createVariation(this.state.project, seed, options);
    const report = formatVariationReport(result.changes);
    this.state.runtime.lastVariationReport = report;
    this.loadProject(result.project, '');
    this.panel.setVariationReport(`${title} (seed ${seed})\n${report}`);
    this.notify(`${title} · seed ${seed}\n${report}`, 'info');
  }

  // ------------------------------------------------------------------ câmera/iluminação

  private applyCameraMode(mode: CameraMode): void {
    const camera = this.state.project.camera;
    Object.assign(camera, CAMERA_MODE_DEFAULTS[mode]);
    camera.mode = mode;
    this.panel.refresh();
    this.onSettingsChanged(['camera'], true);
  }

  private fitCameraNow(): void {
    const project = this.state.project;
    const camera = project.camera;
    const sphere = this.sceneManager.simulation.path.boundingSphere;
    const distance = computeFitDistance(
      sphere.radius,
      camera.fov,
      project.output.width / project.output.height,
      camera.framingMargin,
    );
    const dir = {
      x: camera.position.x - camera.target.x,
      y: camera.position.y - camera.target.y,
      z: camera.position.z - camera.target.z,
    };
    const length = Math.hypot(dir.x, dir.y, dir.z) || 1;
    Object.assign(
      camera.target,
      round3({ x: sphere.center.x, y: sphere.center.y, z: sphere.center.z }),
    );
    Object.assign(
      camera.position,
      round3({
        x: camera.target.x + (dir.x / length) * distance,
        y: camera.target.y + (dir.y / length) * distance,
        z: camera.target.z + (dir.z / length) * distance,
      }),
    );
    camera.distance = Math.min(50, Math.max(2, Number(distance.toFixed(2))));
    camera.autoFrame = true;
    this.panel.refresh();
    this.onSettingsChanged(['camera'], true);
  }

  private setPortrait(): void {
    const output = this.state.project.output;
    output.resolutionPreset = 'vertical';
    output.width = 1080;
    output.height = 1920;
    this.state.project.camera.autoFrame = true;
    this.panel.refresh();
    this.onSettingsChanged(['output', 'camera', 'background'], true);
  }

  private applyLightingPreset(id: Exclude<LightingPresetId, 'custom'>): void {
    assignDeep(
      this.state.project.lighting as unknown as Record<string, unknown>,
      createLightingPreset(id) as unknown as Record<string, unknown>,
    );
    this.panel.refresh();
    this.onSettingsChanged(['lighting'], true);
  }

  private resetSection(section: SectionKey): void {
    const defaults = createDefaultProject();
    const project = this.state.project;
    // assignDeep preserva a identidade dos objetos ligados aos controles da GUI.
    assignDeep(
      project[section] as unknown as Record<string, unknown>,
      defaults[section] as unknown as Record<string, unknown>,
    );
    const sections: DirtySection[] = [section];
    if (section === 'path') {
      project.track.bankAngle = PATH_PRESET_BANK[project.path.preset] ?? 0;
      this.sceneManager.handles.select(null, false);
      this.state.runtime.selectedPoint = null;
      sections.push('track');
    }
    this.panel.refresh();
    this.onSettingsChanged(sections, true);
    this.notify('Grupo restaurado para os valores padrão.', 'info');
  }

  // ------------------------------------------------------------------ visualização

  private togglePlay(): void {
    this.clock.toggle();
    this.updateTopBar();
  }

  private setPlaying(playing: boolean): void {
    if (playing) this.clock.play();
    else this.clock.pause();
    this.updateTopBar();
  }

  private setHelpersVisible(visible: boolean): void {
    this.state.runtime.helpersVisible = visible;
    this.sceneManager.setHelpersVisible(visible);
    this.statusPanel.setVisible(visible);
    this.updateTopBar();
  }

  private setGuiVisible(visible: boolean): void {
    this.state.runtime.guiVisible = visible;
    this.sidebar.hidden = !visible;
    document.body.classList.toggle('gui-hidden', !visible);
    this.rendererManager.layout();
    this.updateTopBar();
  }

  private setEditorView(enabled: boolean): void {
    this.state.runtime.editorView = enabled;
    this.sceneManager.setEditorView(enabled);
    this.panel.refresh();
    this.updateTopBar();
    if (enabled)
      this.notify('Vista livre: a exportação continua usando a câmera configurada.', 'info');
  }

  private setSafeArea(visible: boolean): void {
    this.state.runtime.showSafeArea = visible;
    this.safeArea.setVisible(visible);
  }

  private applyResolutionPreset(id: ResolutionPresetId): void {
    const output = this.state.project.output;
    output.resolutionPreset = id;
    const preset = RESOLUTION_PRESETS.find((r) => r.id === id);
    if (preset && id !== 'custom') {
      output.width = preset.width;
      output.height = preset.height;
    }
    this.panel.refresh();
    this.onSettingsChanged(['output', 'camera', 'background'], true);
  }

  private updateTopBar(): void {
    const runtime = this.state.runtime;
    this.topBar.update({
      playing: this.clock.isPlaying,
      canUndo: this.history.canUndo,
      canRedo: this.history.canRedo,
      helpersVisible: runtime.helpersVisible,
      guiVisible: runtime.guiVisible,
      editorView: runtime.editorView,
    });
  }

  private updateExportInfo(): void {
    const { output, loop } = this.state.project;
    const plan = resolveExportPlan(output, loop);
    const adjusted = plan.durationSeconds !== output.durationSeconds ? ' (ajustada ao loop)' : '';
    const size = formatBytes(estimateFileSizeBytes(output.bitrateMbps, plan.durationSeconds));
    this.panel.setExportInfo(
      `Vídeo: ${output.width}×${output.height} · ${plan.durationSeconds}s${adjusted} · ${plan.totalFrames} frames · ~${size}`,
    );
  }

  private updateStatus(): void {
    const project = this.state.project;
    const snapshot = this.perf.getSnapshot();
    const stats = this.sceneManager.getStats();
    const plan = resolveExportPlan(project.output, project.loop);
    this.statusPanel.update({
      performance: snapshot,
      drawCalls: stats.drawCalls,
      triangles: stats.triangles,
      memoryBytes: stats.memoryBytes,
      curveClosed: project.path.closed,
      curveValid: this.pathValidation.valid,
      seed: project.seed,
      marbleCount: project.marbles.count,
      loopSeconds: project.loop.durationSeconds,
      estimatedFileBytes: estimateFileSizeBytes(project.output.bitrateMbps, plan.durationSeconds),
      exportSeconds: plan.durationSeconds,
      recordingElapsedMs:
        this.recordingStartedAt === null ? null : performance.now() - this.recordingStartedAt,
      recommendations: getPerformanceRecommendations(
        {
          marbleCount: project.marbles.count,
          shadowsEnabled: project.lighting.shadowsEnabled,
          trackSegments: project.track.segmentCount,
          shadowResolution: project.lighting.shadowResolution,
          pixelRatio: this.state.runtime.maxPixelRatio,
        },
        snapshot.sampleCount >= 30 ? snapshot.level : 'good',
      ),
    });
  }

  // ------------------------------------------------------------------ presets

  private getPresetOptions(): Record<string, string> {
    const options: Record<string, string> = {};
    for (const preset of BUILT_IN_PRESETS) options[`★ ${preset.name}`] = `builtin:${preset.name}`;
    for (const name of this.presetStore.listUserPresets()) options[name] = `user:${name}`;
    return options;
  }

  private savePreset(name: string): void {
    try {
      const saved = this.presetStore.saveUserPreset(this.state.project, name);
      this.state.project.name = saved.name;
      this.state.runtime.dirtySinceSave = false;
      this.panel.refreshPresetOptions(`user:${saved.name}`);
      this.panel.refresh();
      this.saveDraft();
      this.notify(`Preset "${saved.name}" salvo no navegador.`, 'success');
    } catch (error) {
      this.errors.report(error, 'Não foi possível salvar o preset');
    }
  }

  private loadPresetByKey(key: string): void {
    if (key.startsWith('builtin:')) {
      const preset = findBuiltInPreset(key.slice('builtin:'.length));
      if (preset) this.loadProject(preset, `Preset "${preset.name}" carregado.`);
      return;
    }
    if (key.startsWith('user:')) {
      const name = key.slice('user:'.length);
      const result = this.presetStore.loadUserPreset(name);
      if (!result) {
        this.notify(`Preset "${name}" não encontrado.`, 'error');
      } else if (!result.ok) {
        this.showInvalidPreset(result.errors);
      } else {
        this.loadProject(result.preset, `Preset "${name}" carregado.`);
      }
      return;
    }
    this.notify('Selecione um preset na lista.', 'info');
  }

  private deletePreset(key: string): void {
    if (!key.startsWith('user:')) {
      this.notify('Presets built-in (★) não podem ser excluídos.', 'warning');
      return;
    }
    const name = key.slice('user:'.length);
    if (!window.confirm(`Excluir o preset "${name}"?`)) return;
    this.presetStore.deleteUserPreset(name);
    this.panel.refreshPresetOptions();
    this.notify(`Preset "${name}" excluído.`, 'info');
  }

  private exportJson(): void {
    const project = { ...this.state.project, timestamp: Date.now() };
    downloadText(serializePreset(project), buildExportFileName(project, 'json'));
    this.state.runtime.dirtySinceSave = false;
    this.notify('Preset exportado como JSON.', 'success');
  }

  private async importFile(file: File): Promise<void> {
    try {
      this.importJsonText(await file.text(), file.name);
    } catch (error) {
      this.errors.report(error, `Falha ao ler "${file.name}"`);
    }
  }

  importJsonText(text: string, source = 'arquivo'): boolean {
    const result = deserializePreset(text);
    if (!result.ok) {
      this.showInvalidPreset(result.errors, source);
      return false;
    }
    const migrated =
      result.migratedFrom !== null ? ` (migrado do schema v${result.migratedFrom})` : '';
    this.loadProject(result.preset, `Preset "${result.preset.name}" importado${migrated}.`);
    if (result.warnings.length > 0) {
      this.notify(
        `${result.warnings.length} aviso(s) na importação:\n${result.warnings.slice(0, 3).join('\n')}`,
        'warning',
      );
    }
    return true;
  }

  private showInvalidPreset(errors: readonly string[], source = 'preset'): void {
    const list = errors
      .slice(0, 5)
      .map((e) => `• ${e}`)
      .join('\n');
    const more = errors.length > 5 ? `\n… e mais ${errors.length - 5} erro(s).` : '';
    this.notify(`Preset inválido (${source}):\n${list}${more}`, 'error', {
      label: 'Restaurar padrão',
      run: () => this.loadProject(createDefaultProject(), 'Projeto padrão restaurado.'),
    });
  }

  // ------------------------------------------------------------------ captura (CaptureHost)

  beginCapture(exportFps: number): void {
    this.flushPending();
    this.capturing = true;
    this.rendererManager.beginCapture();
    this.sceneManager.setCaptureMode(true);
    document.body.classList.add('is-capturing');
    this.clock.beginExport(exportFps);
    const clean = this.isCaptureClean();
    if (!clean.helpersHidden || !clean.guiHidden) {
      this.endCapture();
      throw new Error('Não foi possível ocultar helpers/GUI para a captura.');
    }
  }

  endCapture(): void {
    this.clock.endExport();
    document.body.classList.remove('is-capturing');
    this.sceneManager.setCaptureMode(false);
    this.rendererManager.endCapture();
    this.capturing = false;
    this.safeArea.sync();
  }

  renderExportFrame(frameIndex: number): void {
    this.clock.setFrameIndex(frameIndex);
    this.sceneManager.renderAt(this.clock.getNormalizedTime());
  }

  renderNormalizedTime(normalizedTime: number): void {
    this.sceneManager.renderAt(normalizedTime);
  }

  isCaptureClean(): { helpersHidden: boolean; guiHidden: boolean } {
    return {
      helpersHidden: this.sceneManager.helpersHidden,
      guiHidden: getComputedStyle(this.sidebar).display === 'none',
    };
  }

  // ------------------------------------------------------------------ exportação

  private preExportValidation(kind: ExportKind): ReturnType<typeof validateExport> | null {
    this.flushPending();
    const result = validateExport(this.state.project, kind, null);
    if (!result.ok) {
      this.exportProgress.showErrors('Exportação bloqueada', result.errors);
      return null;
    }
    return result;
  }

  private addHistoryEntry(
    kind: ExportHistoryKind,
    fileName: string,
    blob: Blob,
    thumbnail: string,
    durationSeconds: number,
    normalizedTime: number,
  ): void {
    const project = this.state.project;
    const now = Date.now();
    const entry: ExportHistoryEntry = {
      id: this.exportHistory.createId(now),
      kind,
      fileName,
      width: project.output.width,
      height: project.output.height,
      fps: project.output.fps,
      durationSeconds,
      createdAt: now,
      seed: project.seed,
      presetName: project.name,
      thumbnail,
      snapshot: this.state.snapshot(),
      normalizedTime,
    };
    this.sessionBlobs.set(entry.id, blob);
    try {
      this.panel.historyPanel.render(this.exportHistory.add(entry));
    } catch (error) {
      this.errors.report(error, 'Histórico não atualizado');
    }
  }

  async exportVideo(): Promise<void> {
    if (this.state.runtime.exporting) return;
    const validation = this.preExportValidation('video');
    if (!validation) return;
    const project = this.state.project;
    const { plan } = validation;
    const output = project.output;
    const webCodecsOk =
      output.encoder === 'webCodecs' &&
      (await isWebCodecsSupported(
        webCodecsConfig(output.codec, output.width, output.height, output.fps, output.bitrateMbps),
      ));
    const recorderOk = isVideoRecordingSupported(this.canvas, output.codec);
    for (const warning of validation.warnings) this.notify(warning, 'warning');
    if (output.encoder === 'webCodecs' && !webCodecsOk) {
      this.notify('WebCodecs indisponível neste navegador: usando MediaRecorder.', 'warning');
    }
    if (!webCodecsOk && !recorderOk) {
      this.notify('MediaRecorder/WebM indisponível: exportando sequência PNG em ZIP.', 'warning');
    }

    this.state.runtime.exporting = true;
    this.bus.emit('exportStateChanged', { exporting: true });
    this.exportAbort = new AbortController();
    this.recordingStartedAt = performance.now();
    const format = webCodecsOk
      ? `WebM ${output.codec.toUpperCase()} (WebCodecs)`
      : recorderOk
        ? `WebM ${output.codec.toUpperCase()} (MediaRecorder)`
        : 'ZIP de PNGs';
    this.exportProgress.start(
      'Exportando vídeo',
      `${output.width}×${output.height} · ${plan.durationSeconds}s · ${output.fps} fps · ${format}`,
      webCodecsOk ? 'offline' : 'realtime',
    );
    try {
      const result = await this.videoExporter.export(
        {
          width: output.width,
          height: output.height,
          fps: output.fps,
          totalFrames: plan.totalFrames,
          bitrateMbps: output.bitrateMbps,
          codec: output.codec,
          encoder: output.encoder,
          presetJson: serializePreset(project),
        },
        (progress) => this.exportProgress.update(progress),
        this.exportAbort.signal,
      );
      const fileName = buildExportFileName(project, result.kind === 'zip' ? 'zip' : 'webm');
      downloadBlob(result.blob, fileName);
      this.addHistoryEntry(
        result.kind === 'zip' ? 'zip' : 'video',
        fileName,
        result.blob,
        result.thumbnail,
        plan.durationSeconds,
        0,
      );
      const lagNote =
        result.lagMs > 100
          ? ` Atenção: a renderização atrasou até ${Math.round(result.lagMs)} ms em relação ao tempo real; o timing do vídeo pode variar. Use o encoder WebCodecs (frame-exato) ou reduza sombras/resolução.`
          : '';
      this.exportProgress.finish(
        `${result.kind === 'zip' ? 'Sequência PNG salva!' : 'Vídeo salvo!'} ${fileName} (${formatBytes(result.blob.size)}).${lagNote}`,
        lagNote ? 'warning' : 'success',
        true,
      );
    } catch (error) {
      if (error instanceof ExportCancelledError) {
        this.exportProgress.finish('Exportação cancelada.', 'warning', true);
      } else {
        this.exportProgress.finish(
          `Falha na exportação: ${ErrorHandler.describe(error)}`,
          'error',
          true,
        );
        console.error(error);
      }
    } finally {
      this.state.runtime.exporting = false;
      this.exportAbort = null;
      this.recordingStartedAt = null;
      this.bus.emit('exportStateChanged', { exporting: false });
      if (project.output.autoLoop) this.clock.play();
      this.updateTopBar();
    }
  }

  async capturePng(normalizedTime = this.clock.getNormalizedTime()): Promise<void> {
    if (this.state.runtime.exporting) return;
    if (!this.preExportValidation('image')) return;
    const project = this.state.project;
    try {
      const result = await this.imageExporter.capture(normalizedTime, project.output.fps);
      const fileName = buildExportFileName(project, 'png');
      downloadBlob(result.blob, fileName);
      this.addHistoryEntry('image', fileName, result.blob, result.thumbnail, 0, normalizedTime);
      this.notify(`PNG salvo: ${fileName} (${result.width}×${result.height}).`, 'success');
    } catch (error) {
      this.errors.report(error, 'Falha ao capturar PNG');
    }
  }

  private async redownload(entry: ExportHistoryEntry): Promise<void> {
    const blob = this.sessionBlobs.get(entry.id);
    if (blob) {
      downloadBlob(blob, entry.fileName);
      return;
    }
    const ok = window.confirm(
      'O arquivo não está mais em memória. Re-renderizar a partir das configurações salvas? O projeto atual será substituído (Ctrl+Z desfaz).',
    );
    if (!ok) return;
    const result = deserializePreset(entry.snapshot);
    if (!result.ok) {
      this.showInvalidPreset(result.errors, 'histórico');
      return;
    }
    this.loadProject(result.preset, 'Configurações da exportação restauradas.', 'info');
    if (entry.kind === 'image') await this.capturePng(entry.normalizedTime);
    else await this.exportVideo();
  }

  /**
   * Autoverificação: renderiza o mesmo frame pelo caminho do preview (relógio em tempo real)
   * e pelo caminho do export (índice de frame), na resolução final, e compara os pixels.
   */
  async verifyDeterminism(): Promise<DeterminismReport | null> {
    if (this.state.runtime.exporting) return null;
    this.flushPending();
    const project = this.state.project;
    const fps = project.loop.fps;
    const duration = project.loop.durationSeconds;
    const framesPerLoop = computeTotalFrames(duration, fps);
    const frameIndex = Math.floor(framesPerLoop * 0.37);

    let fakeNow = 0;
    const previewClock = new LoopClock({ durationSeconds: duration, fps, now: () => fakeNow });
    fakeNow = (frameIndex / fps) * 1000 + 1;
    const previewTime = previewClock.getNormalizedTime();
    const exportClock = new LoopClock({ durationSeconds: duration, fps });
    exportClock.beginExport(fps);
    exportClock.setFrameIndex(frameIndex);
    const exportTime = exportClock.getNormalizedTime();

    const gl = this.rendererManager.renderer.getContext();
    this.beginCapture(fps);
    let report: DeterminismReport;
    try {
      const width = this.canvas.width;
      const height = this.canvas.height;
      const read = (): Uint8Array => {
        const buffer = new Uint8Array(width * height * 4);
        gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, buffer);
        return buffer;
      };
      this.sceneManager.renderAt(previewTime);
      const a = read();
      this.sceneManager.renderAt(exportTime);
      const b = read();
      this.sceneManager.renderAt(previewTime);
      const c = read();
      let maxDiff = 0;
      let repeatDiff = 0;
      let differing = 0;
      for (let i = 0; i < a.length; i++) {
        const d = Math.abs((a[i] as number) - (b[i] as number));
        if (d > maxDiff) maxDiff = d;
        if (d > 2) differing++;
        const r = Math.abs((a[i] as number) - (c[i] as number));
        if (r > repeatDiff) repeatDiff = r;
      }
      report = {
        frameIndex,
        previewTime,
        exportTime,
        timesIdentical: previewTime === exportTime,
        maxChannelDiff: maxDiff,
        repeatMaxChannelDiff: repeatDiff,
        differingPixels: differing,
        passed: previewTime === exportTime && maxDiff <= 2 && repeatDiff <= 2,
      };
    } finally {
      this.endCapture();
    }
    await yieldToBrowser();
    this.notify(
      `${report.passed ? '✓ Determinismo verificado' : '✗ Divergência detectada'} — frame ${frameIndex}: ` +
        `t(preview)=${previewTime.toFixed(6)}, t(export)=${exportTime.toFixed(6)}; ` +
        `diferença máx. ${report.maxChannelDiff} (repetição ${report.repeatMaxChannelDiff}) níveis RGBA, tolerância 2.`,
      report.passed ? 'success' : 'error',
    );
    return report;
  }
}

function round3(v: Vec3Like): Vec3Like {
  return { x: Number(v.x.toFixed(3)), y: Number(v.y.toFixed(3)), z: Number(v.z.toFixed(3)) };
}

/** Cede o controle ao navegador (permite repintar após a captura). */
function yieldToBrowser(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}
