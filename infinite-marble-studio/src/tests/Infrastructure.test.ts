import { BoxGeometry, Mesh, MeshStandardMaterial, PerspectiveCamera, Scene, Texture } from 'three';
import { describe, expect, it, vi } from 'vitest';
import { disposeObject3D } from '../core/Disposable';
import { createRandomSeed } from '../core/SeedSource';
import { PathHandles } from '../path/PathHandles';
import { createPresetPoints } from '../path/PathFactory';

/** Elemento mínimo para instanciar controles sem navegador. */
function fakeElement(): HTMLElement {
  const listeners = new Map<string, Set<(event: unknown) => void>>();
  return {
    style: {},
    addEventListener: (type: string, fn: (event: unknown) => void) => {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(fn);
    },
    removeEventListener: (type: string, fn: (event: unknown) => void) =>
      listeners.get(type)?.delete(fn),
    dispatch: (type: string, event: unknown) => listeners.get(type)?.forEach((fn) => fn(event)),
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }),
    ownerDocument: { addEventListener: () => undefined, removeEventListener: () => undefined },
    getRootNode: () => ({
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }),
    setPointerCapture: () => undefined,
    releasePointerCapture: () => undefined,
  } as unknown as HTMLElement;
}

describe('Disposable', () => {
  it('disposeObject3D libera geometrias, materiais e texturas da subárvore', () => {
    const scene = new Scene();
    const texture = new Texture();
    const material = new MeshStandardMaterial({ map: texture });
    const geometry = new BoxGeometry();
    const parent = new Mesh(geometry, material);
    parent.add(new Mesh(new BoxGeometry(), new MeshStandardMaterial()));
    scene.add(parent);
    const spies = [
      vi.spyOn(texture, 'dispose'),
      vi.spyOn(material, 'dispose'),
      vi.spyOn(geometry, 'dispose'),
    ];
    disposeObject3D(parent);
    for (const spy of spies) expect(spy).toHaveBeenCalled();
    expect(parent.parent).toBeNull();
  });
});

describe('SeedSource', () => {
  it('gera seeds inteiras de 32 bits', () => {
    for (let i = 0; i < 20; i++) {
      const seed = createRandomSeed();
      expect(Number.isInteger(seed)).toBe(true);
      expect(seed).toBeGreaterThanOrEqual(0);
      expect(seed).toBeLessThanOrEqual(0xffffffff);
    }
  });
});

describe('PathHandles', () => {
  it('cria um handle por ponto, seleciona e acompanha mudanças', () => {
    const scene = new Scene();
    const element = fakeElement();
    const handles = new PathHandles(scene, new PerspectiveCamera(), element);
    const points = createPresetPoints('wave3d');
    handles.setPoints(points, true);
    expect(handles.group.children).toHaveLength(points.length);
    expect(scene.getObjectByName('control-polygon')).toBeDefined();

    const onSelect = vi.fn();
    handles.onSelect = onSelect;
    handles.select(3);
    expect(handles.selectedIndex).toBe(3);
    expect(onSelect).toHaveBeenCalledWith(3);

    handles.setPoints(points.slice(0, 2), true);
    expect(handles.group.children).toHaveLength(2);
    expect(handles.selectedIndex).toBeNull();

    handles.setVisible(false);
    expect(handles.group.visible).toBe(false);
    expect(handles.isDragging).toBe(false);
    handles.setCamera(new PerspectiveCamera());
    handles.dispose();
    expect(scene.getObjectByName('path-handles')).toBeUndefined();
  });

  it('clique sem arrasto seleciona o handle atingido pelo raio', () => {
    const scene = new Scene();
    const element = fakeElement() as HTMLElement & { dispatch(type: string, e: unknown): void };
    const camera = new PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.set(0, 0, 10);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld();
    const handles = new PathHandles(scene, camera, element);
    handles.setPoints(
      [
        { x: 0, y: 0, z: 0 },
        { x: 3, y: 0, z: 0 },
        { x: 3, y: 3, z: 0 },
        { x: 0, y: 3, z: 0 },
      ],
      true,
    );
    scene.updateMatrixWorld(true);
    // O TransformControls também escuta os eventos e consulta `document`.
    vi.stubGlobal('document', { pointerLockElement: null });
    const pointer = {
      clientX: 50,
      clientY: 50,
      button: 0,
      pointerType: 'mouse',
      pointerId: 1,
      isPrimary: true,
    };
    element.dispatch('pointerdown', pointer);
    element.dispatch('pointerup', pointer);
    vi.unstubAllGlobals();
    expect(handles.selectedIndex).toBe(0);
    handles.dispose();
  });
});
