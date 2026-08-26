import { describe, expect, it } from "vitest";
import { BlobSource, base64ToBlob, selectBasemapSource } from "./basemapSource.js";

describe("base64ToBlob", () => {
  it("round-trips a known byte sequence", async () => {
    const originalBytes = new Uint8Array([80, 77, 84, 105, 108, 101, 115, 3, 0, 255, 16]);
    const base64 = btoa(String.fromCharCode(...originalBytes));

    const blob = base64ToBlob(base64);
    const roundTripped = new Uint8Array(await blob.arrayBuffer());

    expect(roundTripped).toEqual(originalBytes);
  });

  it("round-trips an empty string to an empty blob", async () => {
    const blob = base64ToBlob("");

    expect(blob.size).toBe(0);
  });
});

describe("BlobSource", () => {
  it("getBytes returns the correct byte range from the underlying blob", async () => {
    const bytes = new Uint8Array([10, 20, 30, 40, 50, 60, 70, 80]);
    const source = new BlobSource(new Blob([bytes]));

    const { data } = await source.getBytes(2, 3);

    expect(new Uint8Array(data)).toEqual(new Uint8Array([30, 40, 50]));
  });

  it("getBytes at offset 0 returns the leading bytes", async () => {
    const bytes = new Uint8Array([1, 2, 3, 4, 5]);
    const source = new BlobSource(new Blob([bytes]));

    const { data } = await source.getBytes(0, 2);

    expect(new Uint8Array(data)).toEqual(new Uint8Array([1, 2]));
  });

  it("getKey returns a stable string across calls", () => {
    const source = new BlobSource(new Blob([new Uint8Array([1])]));

    const first = source.getKey();
    const second = source.getKey();

    expect(typeof first).toBe("string");
    expect(first).toBe(second);
  });

  it("getKey is stable across two different instances", () => {
    const a = new BlobSource(new Blob([new Uint8Array([1])]));
    const b = new BlobSource(new Blob([new Uint8Array([2])]));

    expect(a.getKey()).toBe(b.getKey());
  });
});

// research.md §8: hosted mode needs no custom Source at all -- passing a
// plain URL string straight through to `new pmtiles.PMTiles(url)` makes it
// use the package's own default FetchSource, exactly like every other
// PMTiles deployment on the web.
describe("selectBasemapSource", () => {
  it("returns the plain URL string for hosted mode", () => {
    const basemap = { mode: "hosted", url: "https://example.com/basemap.pmtiles" };

    const source = selectBasemapSource(basemap, {});

    expect(source).toBe("https://example.com/basemap.pmtiles");
  });

  it("returns a BlobSource decoded from window[basemap.variable] for embedded mode", async () => {
    const originalBytes = new Uint8Array([80, 77, 84, 105, 108, 101, 115, 3]);
    const base64 = btoa(String.fromCharCode(...originalBytes));
    const basemap = { mode: "embedded", file: "basemap-pmtiles.js", variable: "RKBY_PMTILES_BASE64" };
    const fakeWindow = { RKBY_PMTILES_BASE64: base64 };

    const source = selectBasemapSource(basemap, fakeWindow);

    expect(source).toBeInstanceOf(BlobSource);
    const { data } = await source.getBytes(0, originalBytes.length);
    expect(new Uint8Array(data)).toEqual(originalBytes);
  });
});
