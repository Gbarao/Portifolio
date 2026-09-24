import type { Axis } from '../path/PathEditor';
import type { Vec3Like } from '../presets/PresetSchema';
import { button, el } from './dom';

export interface PointTableActions {
  select(index: number): void;
  remove(index: number): void;
  setCoordinate(index: number, axis: Axis, value: number): void;
}

const AXES: readonly Axis[] = ['x', 'y', 'z'];

/** Tabela HTML com os pontos de controle: índice, X, Y, Z, selecionar, excluir. */
export class PointTable {
  readonly element: HTMLElement;
  private readonly body: HTMLTableSectionElement;
  private points: readonly Vec3Like[] = [];
  private selected: number | null = null;

  constructor(private readonly actions: PointTableActions) {
    this.body = el('tbody');
    const head = el('thead', {}, [
      el(
        'tr',
        {},
        ['#', 'X', 'Y', 'Z', '', ''].map((h) => el('th', { scope: 'col' }, [h])),
      ),
    ]);
    const table = el(
      'table',
      { className: 'point-table', 'aria-label': 'Pontos de controle do trajeto' },
      [head, this.body],
    );
    this.element = el('div', { className: 'point-table-wrap' }, [table]);
  }

  render(points: readonly Vec3Like[], selected: number | null): void {
    const sameCount = points.length === this.points.length;
    this.points = points;
    this.selected = selected;
    if (!sameCount || this.body.rows.length !== points.length) {
      this.body.replaceChildren(...points.map((p, i) => this.createRow(p, i)));
    } else {
      points.forEach((p, i) => this.updateRow(this.body.rows[i] as HTMLTableRowElement, p, i));
    }
    const row = selected === null ? null : this.body.rows[selected];
    row?.scrollIntoView({ block: 'nearest' });
  }

  private createRow(point: Vec3Like, index: number): HTMLTableRowElement {
    const inputs = AXES.map((axis) => {
      const input = el('input', {
        type: 'number',
        step: '0.1',
        className: 'coord-input',
        'aria-label': `Ponto ${index} ${axis.toUpperCase()}`,
        title: `Coordenada ${axis.toUpperCase()} do ponto ${index}`,
      });
      input.addEventListener('change', () => {
        const value = Number(input.value);
        if (Number.isFinite(value)) this.actions.setCoordinate(index, axis, value);
      });
      return el('td', {}, [input]);
    });
    const row = el('tr', {}, [
      el('td', { className: 'point-index' }, [String(index)]),
      ...inputs,
      el('td', {}, [
        button(
          '◎',
          `Selecionar ponto ${index}`,
          () => this.actions.select(index),
          'btn btn-icon btn-small',
        ),
      ]),
      el('td', {}, [
        button(
          '✕',
          `Excluir ponto ${index}`,
          () => this.actions.remove(index),
          'btn btn-icon btn-small btn-danger',
        ),
      ]),
    ]);
    this.updateRow(row, point, index);
    return row;
  }

  private updateRow(row: HTMLTableRowElement, point: Vec3Like, index: number): void {
    row.classList.toggle('selected', index === this.selected);
    const inputs = row.querySelectorAll<HTMLInputElement>('input.coord-input');
    AXES.forEach((axis, i) => {
      const input = inputs[i];
      // Não sobrescreve o campo que o usuário está editando.
      if (input && document.activeElement !== input) input.value = point[axis].toFixed(3);
    });
  }
}
