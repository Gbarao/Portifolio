/**
 * Muxer WebM (Matroska) mínimo para uma trilha de vídeo VP8/VP9, usado com WebCodecs.
 * Escreve EBML header, Segment (Info com Duration, Tracks, Clusters com SimpleBlocks e Cues).
 * Timestamps em milissegundos (TimecodeScale = 1 000 000 ns).
 */

export type WebmCodecId = 'V_VP8' | 'V_VP9';

export interface WebmChunk {
  data: Uint8Array;
  /** Timestamp em microssegundos. */
  timestampUs: number;
  keyFrame: boolean;
}

export interface WebmMuxerOptions {
  codecId: WebmCodecId;
  width: number;
  height: number;
  frameRate: number;
  /** Duração total em milissegundos. */
  durationMs: number;
}

const encoder = new TextEncoder();

function concat(parts: readonly Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, p) => sum + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function idBytes(id: number): Uint8Array {
  const bytes: number[] = [];
  let value = id;
  while (value > 0) {
    bytes.unshift(value & 0xff);
    value = Math.floor(value / 256);
  }
  return new Uint8Array(bytes);
}

/** Tamanho EBML (vint) com o menor comprimento possível. */
export function encodeVint(value: number): Uint8Array {
  for (let length = 1; length <= 8; length++) {
    if (value < 2 ** (7 * length) - 1) {
      const out = new Uint8Array(length);
      let v = value;
      for (let i = length - 1; i >= 0; i--) {
        out[i] = v & 0xff;
        v = Math.floor(v / 256);
      }
      out[0] = (out[0] as number) | (1 << (8 - length));
      return out;
    }
  }
  throw new Error('Elemento EBML grande demais.');
}

function element(id: number, payload: Uint8Array): Uint8Array {
  return concat([idBytes(id), encodeVint(payload.length), payload]);
}

function master(id: number, children: readonly Uint8Array[]): Uint8Array {
  return element(id, concat(children));
}

function uint(id: number, value: number): Uint8Array {
  const bytes: number[] = [];
  let v = Math.max(0, Math.floor(value));
  do {
    bytes.unshift(v & 0xff);
    v = Math.floor(v / 256);
  } while (v > 0);
  return element(id, new Uint8Array(bytes));
}

function float64(id: number, value: number): Uint8Array {
  const payload = new Uint8Array(8);
  new DataView(payload.buffer).setFloat64(0, value);
  return element(id, payload);
}

function text(id: number, value: string): Uint8Array {
  return element(id, encoder.encode(value));
}

const ID = {
  EBML: 0x1a45dfa3,
  EBMLVersion: 0x4286,
  EBMLReadVersion: 0x42f7,
  EBMLMaxIDLength: 0x42f2,
  EBMLMaxSizeLength: 0x42f3,
  DocType: 0x4282,
  DocTypeVersion: 0x4287,
  DocTypeReadVersion: 0x4285,
  Segment: 0x18538067,
  Info: 0x1549a966,
  TimecodeScale: 0x2ad7b1,
  Duration: 0x4489,
  MuxingApp: 0x4d80,
  WritingApp: 0x5741,
  Tracks: 0x1654ae6b,
  TrackEntry: 0xae,
  TrackNumber: 0xd7,
  TrackUID: 0x73c5,
  TrackType: 0x83,
  FlagLacing: 0x9c,
  CodecID: 0x86,
  DefaultDuration: 0x23e383,
  Video: 0xe0,
  PixelWidth: 0xb0,
  PixelHeight: 0xba,
  Cluster: 0x1f43b675,
  Timecode: 0xe7,
  SimpleBlock: 0xa3,
  Cues: 0x1c53bb6b,
  CuePoint: 0xbb,
  CueTime: 0xb3,
  CueTrackPositions: 0xb7,
  CueTrack: 0xf7,
  CueClusterPosition: 0xf1,
} as const;

export const WEBM_IDS = ID;

function simpleBlock(chunk: WebmChunk, relativeMs: number): Uint8Array {
  const header = new Uint8Array(4);
  header[0] = 0x81; // trilha 1 (vint)
  new DataView(header.buffer).setInt16(1, relativeMs);
  header[3] = chunk.keyFrame ? 0x80 : 0x00;
  return element(ID.SimpleBlock, concat([header, chunk.data]));
}

/** Monta o arquivo WebM completo a partir dos chunks codificados (em ordem). */
export function muxWebm(chunks: readonly WebmChunk[], options: WebmMuxerOptions): Uint8Array {
  if (chunks.length === 0) throw new Error('Nenhum frame codificado.');
  if (!chunks[0]?.keyFrame) throw new Error('O primeiro frame precisa ser keyframe.');
  const appName = 'Infinite Marble Studio';
  const header = master(ID.EBML, [
    uint(ID.EBMLVersion, 1),
    uint(ID.EBMLReadVersion, 1),
    uint(ID.EBMLMaxIDLength, 4),
    uint(ID.EBMLMaxSizeLength, 8),
    text(ID.DocType, 'webm'),
    uint(ID.DocTypeVersion, 4),
    uint(ID.DocTypeReadVersion, 2),
  ]);
  const info = master(ID.Info, [
    uint(ID.TimecodeScale, 1_000_000),
    float64(ID.Duration, options.durationMs),
    text(ID.MuxingApp, appName),
    text(ID.WritingApp, appName),
  ]);
  const tracks = master(ID.Tracks, [
    master(ID.TrackEntry, [
      uint(ID.TrackNumber, 1),
      uint(ID.TrackUID, 1),
      uint(ID.TrackType, 1),
      uint(ID.FlagLacing, 0),
      text(ID.CodecID, options.codecId),
      uint(ID.DefaultDuration, Math.round(1e9 / options.frameRate)),
      master(ID.Video, [uint(ID.PixelWidth, options.width), uint(ID.PixelHeight, options.height)]),
    ]),
  ]);

  // Um cluster por keyframe (ou a cada 30 s): timecodes relativos cabem em int16.
  const clusters: Uint8Array[] = [];
  const cuePoints: Uint8Array[] = [];
  let offset = info.length + tracks.length;
  let current: { timecode: number; blocks: Uint8Array[] } | null = null;
  const flush = (): void => {
    if (!current) return;
    const cluster = master(ID.Cluster, [uint(ID.Timecode, current.timecode), ...current.blocks]);
    cuePoints.push(
      master(ID.CuePoint, [
        uint(ID.CueTime, current.timecode),
        master(ID.CueTrackPositions, [uint(ID.CueTrack, 1), uint(ID.CueClusterPosition, offset)]),
      ]),
    );
    clusters.push(cluster);
    offset += cluster.length;
    current = null;
  };
  for (const chunk of chunks) {
    const ms = Math.round(chunk.timestampUs / 1000);
    if (!current || chunk.keyFrame || ms - current.timecode > 30_000) {
      flush();
      current = { timecode: ms, blocks: [] };
    }
    current.blocks.push(simpleBlock(chunk, ms - current.timecode));
  }
  flush();

  const segment = master(ID.Segment, [info, tracks, ...clusters, master(ID.Cues, cuePoints)]);
  return concat([header, segment]);
}

// ---------------------------------------------------------------------------
// Leitor mínimo (usado nos testes e para inspeção de arquivos gerados).
// ---------------------------------------------------------------------------

export interface WebmBlockInfo {
  timecodeMs: number;
  keyFrame: boolean;
  size: number;
}

function readVint(
  bytes: Uint8Array,
  offset: number,
  keepMarker: boolean,
): { value: number; length: number } {
  const first = bytes[offset] as number;
  let length = 1;
  let mask = 0x80;
  while (length <= 8 && !(first & mask)) {
    mask >>= 1;
    length++;
  }
  let value = keepMarker ? first : first & (mask - 1);
  for (let i = 1; i < length; i++) value = value * 256 + (bytes[offset + i] as number);
  return { value, length };
}

// BlockGroup (0xA0) / Block (0xA1): formato usado pelo MediaRecorder do Chromium.
const BLOCK_GROUP = 0xa0;
const BLOCK = 0xa1;
const CONTAINERS = new Set<number>([ID.Segment, ID.Cluster, BLOCK_GROUP]);

/** Lista os blocos (timecode absoluto em ms) de um WebM. Suporta tamanhos desconhecidos. */
export function readWebmBlocks(bytes: Uint8Array): {
  blocks: WebmBlockInfo[];
  durationMs: number | null;
} {
  const blocks: WebmBlockInfo[] = [];
  let clusterTimecode = 0;
  let durationMs: number | null = null;
  let offset = 0;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  while (offset < bytes.length) {
    const id = readVint(bytes, offset, true);
    const size = readVint(bytes, offset + id.length, false);
    const body = offset + id.length + size.length;
    if (CONTAINERS.has(id.value) || id.value === ID.Info) {
      offset = body;
      continue;
    }
    if (id.value === ID.Duration && size.value === 8) durationMs = view.getFloat64(body);
    if (id.value === ID.Timecode) {
      clusterTimecode = 0;
      for (let i = 0; i < size.value; i++)
        clusterTimecode = clusterTimecode * 256 + (bytes[body + i] as number);
    }
    if (id.value === ID.SimpleBlock || id.value === BLOCK) {
      const track = readVint(bytes, body, false);
      const relative = view.getInt16(body + track.length);
      const flags = bytes[body + track.length + 2] as number;
      blocks.push({
        timecodeMs: clusterTimecode + relative,
        keyFrame: id.value === ID.SimpleBlock && (flags & 0x80) !== 0,
        size: size.value - track.length - 3,
      });
    }
    offset = body + size.value;
  }
  return { blocks, durationMs };
}
