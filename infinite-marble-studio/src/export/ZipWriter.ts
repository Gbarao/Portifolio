const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

export function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    crc = (CRC_TABLE[(crc ^ (data[i] as number)) & 0xff] as number) ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

interface ZipEntry {
  name: Uint8Array;
  crc: number;
  size: number;
  offset: number;
}

const MAX_ZIP_BYTES = 0xffffffff;

/**
 * Escritor ZIP mínimo (método STORE, sem compressão): adequado para PNGs, que já são
 * comprimidos. Usado como fallback quando MediaRecorder não está disponível.
 */
export class ZipWriter {
  private readonly entries: ZipEntry[] = [];
  private readonly chunks: Uint8Array<ArrayBuffer>[] = [];
  private offset = 0;
  private readonly encoder = new TextEncoder();
  private readonly dosTime: number;
  private readonly dosDate: number;

  constructor(date: Date = new Date(2024, 0, 1)) {
    this.dosTime = (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1);
    this.dosDate =
      ((Math.max(1980, date.getFullYear()) - 1980) << 9) |
      ((date.getMonth() + 1) << 5) |
      date.getDate();
  }

  get fileCount(): number {
    return this.entries.length;
  }

  get byteLength(): number {
    return this.offset;
  }

  addFile(name: string, data: Uint8Array): void {
    const nameBytes = this.encoder.encode(name);
    const total = this.offset + 30 + nameBytes.length + data.length;
    if (total > MAX_ZIP_BYTES) {
      throw new Error('O ZIP excederia 4 GB. Reduza a duração, o FPS ou a resolução.');
    }
    const header = new Uint8Array(30 + nameBytes.length);
    const view = new DataView(header.buffer);
    const crc = crc32(data);
    view.setUint32(0, 0x04034b50, true);
    view.setUint16(4, 20, true);
    view.setUint16(6, 0x0800, true); // nomes em UTF-8
    view.setUint16(8, 0, true); // STORE
    view.setUint16(10, this.dosTime, true);
    view.setUint16(12, this.dosDate, true);
    view.setUint32(14, crc, true);
    view.setUint32(18, data.length, true);
    view.setUint32(22, data.length, true);
    view.setUint16(26, nameBytes.length, true);
    view.setUint16(28, 0, true);
    header.set(nameBytes, 30);
    this.entries.push({ name: nameBytes, crc, size: data.length, offset: this.offset });
    this.chunks.push(header, new Uint8Array(data));
    this.offset += header.length + data.length;
  }

  addText(name: string, text: string): void {
    this.addFile(name, this.encoder.encode(text));
  }

  private buildCentralDirectory(): Uint8Array<ArrayBuffer>[] {
    const parts: Uint8Array<ArrayBuffer>[] = [];
    let size = 0;
    for (const entry of this.entries) {
      const record = new Uint8Array(46 + entry.name.length);
      const view = new DataView(record.buffer);
      view.setUint32(0, 0x02014b50, true);
      view.setUint16(4, 20, true);
      view.setUint16(6, 20, true);
      view.setUint16(8, 0x0800, true);
      view.setUint16(10, 0, true);
      view.setUint16(12, this.dosTime, true);
      view.setUint16(14, this.dosDate, true);
      view.setUint32(16, entry.crc, true);
      view.setUint32(20, entry.size, true);
      view.setUint32(24, entry.size, true);
      view.setUint16(28, entry.name.length, true);
      view.setUint16(30, 0, true);
      view.setUint16(32, 0, true);
      view.setUint16(34, 0, true);
      view.setUint16(36, 0, true);
      view.setUint32(38, 0, true);
      view.setUint32(42, entry.offset, true);
      record.set(entry.name, 46);
      parts.push(record);
      size += record.length;
    }
    const end = new Uint8Array(22);
    const view = new DataView(end.buffer);
    view.setUint32(0, 0x06054b50, true);
    view.setUint16(4, 0, true);
    view.setUint16(6, 0, true);
    view.setUint16(8, this.entries.length, true);
    view.setUint16(10, this.entries.length, true);
    view.setUint32(12, size, true);
    view.setUint32(16, this.offset, true);
    view.setUint16(20, 0, true);
    parts.push(end);
    return parts;
  }

  finishBytes(): Uint8Array {
    const parts = [...this.chunks, ...this.buildCentralDirectory()];
    const total = parts.reduce((sum, p) => sum + p.length, 0);
    const out = new Uint8Array(total);
    let cursor = 0;
    for (const part of parts) {
      out.set(part, cursor);
      cursor += part.length;
    }
    return out;
  }

  finish(): Blob {
    return new Blob([...this.chunks, ...this.buildCentralDirectory()], { type: 'application/zip' });
  }
}
