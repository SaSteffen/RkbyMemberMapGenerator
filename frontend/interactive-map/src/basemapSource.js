// Bridges the base64-embedded PMTiles archive (research.md §2) into
// pmtiles's own public Source interface, entirely from in-memory bytes --
// no network request, which is what makes this work when index.html is
// opened via file://: a real Chromium binary blocks fetch()/XHR of a
// sibling local file from a file://-opened page (research.md §2's
// empirical finding), so the archive's bytes have to already be in memory
// (decoded from the classic-script global basemap-pmtiles.js sets) rather
// than fetched on demand.

export function base64ToBlob(base64String) {
  const binaryString = atob(base64String);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return new Blob([bytes]);
}

// Satisfies pmtiles's own public Source interface (getBytes/getKey,
// js/src/index.ts) -- pmtiles's built-in FileSource is typed for a
// browser File (which normally requires user-initiated selection), but
// the interface only needs Blob.slice()/.arrayBuffer(), both local memory
// operations a plain Blob supports identically (research.md §2).
export class BlobSource {
  constructor(blob, key = "basemap.pmtiles") {
    this.blob = blob;
    this.key = key;
  }

  getKey() {
    return this.key;
  }

  async getBytes(offset, length) {
    const slice = this.blob.slice(offset, offset + length);
    const data = await slice.arrayBuffer();
    return { data };
  }
}

// data-model.md § Bundled Map Data, research.md §8: picks what to hand
// `new pmtiles.PMTiles(...)` for either build variant. Hosted mode needs no
// custom Source at all -- a plain URL string makes pmtiles use its own
// default FetchSource, exactly like every other PMTiles deployment on the
// web. Embedded mode still routes through the Blob-backed Source above,
// since file://-opened pages can never fetch() a sibling local file
// (research.md §2).
export function selectBasemapSource(basemap, win) {
  if (basemap.mode === "hosted") {
    return basemap.url;
  }
  return new BlobSource(base64ToBlob(win[basemap.variable]));
}
