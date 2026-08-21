import { describe, expect, it } from "vitest";
import {
  classifyFileDrag,
  dataTransferHasFiles,
  fileSuffix,
  formatRejectedUploads,
  isSupportedUploadFile,
  partitionUploadFiles,
  resolveDroppedFiles,
  UNSUPPORTED_UPLOAD_MESSAGE,
} from "./uploadAccept";

function file(name: string, type = ""): File {
  return new File(["hello"], name, { type });
}

describe("uploadAccept", () => {
  it("accepts PDF, Markdown, and plain text by suffix", () => {
    expect(isSupportedUploadFile(file("paper.pdf", "application/pdf"))).toBe(true);
    expect(isSupportedUploadFile(file("notes.md", "text/markdown"))).toBe(true);
    expect(isSupportedUploadFile(file("notes.markdown"))).toBe(true);
    expect(isSupportedUploadFile(file("readme.txt", "text/plain"))).toBe(true);
  });

  it("rejects images and unknown types before any upload", () => {
    expect(isSupportedUploadFile(file("photo.png", "image/png"))).toBe(false);
    expect(isSupportedUploadFile(file("photo.jpg", "image/jpeg"))).toBe(false);
    expect(fileSuffix("photo.png")).toBe(".png");
    expect(resolveDroppedFiles([file("photo.png")]).error).toBe(UNSUPPORTED_UPLOAD_MESSAGE);
  });

  it("keeps supported files when a drop also includes an unsupported type", () => {
    const pdf = file("a.pdf");
    const md = file("b.md");
    const png = file("photo.png");
    const resolved = resolveDroppedFiles([pdf, png, md]);
    expect(resolved.accepted.map((item) => item.name)).toEqual(["a.pdf", "b.md"]);
    expect(resolved.rejected).toEqual([
      { filename: "photo.png", reason: UNSUPPORTED_UPLOAD_MESSAGE },
    ]);
    expect(resolved.error).toBeUndefined();
  });

  it("accepts multiple supported files", () => {
    const pdf = file("a.pdf");
    const md = file("b.md");
    expect(resolveDroppedFiles([pdf, md]).accepted).toEqual([pdf, md]);
  });

  it("accepts a single supported file", () => {
    const pdf = file("a.pdf");
    expect(resolveDroppedFiles([pdf])).toEqual({ accepted: [pdf], rejected: [] });
  });

  it("formats rejected rows", () => {
    expect(
      formatRejectedUploads([{ filename: "x.png", reason: UNSUPPORTED_UPLOAD_MESSAGE }]),
    ).toContain("x.png:");
    expect(partitionUploadFiles([file("ok.md"), file("no.png")]).accepted).toHaveLength(1);
  });

  it("detects a file drag from dataTransfer types", () => {
    expect(dataTransferHasFiles({ types: ["Files"] } as unknown as DataTransfer)).toBe(true);
    expect(dataTransferHasFiles({ types: ["text/plain"] } as unknown as DataTransfer)).toBe(false);
    expect(dataTransferHasFiles(null)).toBe(false);
    expect(classifyFileDrag({ types: ["Files"] } as unknown as DataTransfer)).toBe("files");
    expect(classifyFileDrag({ types: [] } as unknown as DataTransfer)).toBe("unknown");
    expect(classifyFileDrag({ types: ["text/plain"] } as unknown as DataTransfer)).toBe(
      "not-files",
    );
  });
});
