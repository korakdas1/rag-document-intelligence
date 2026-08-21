import { describe, expect, it } from "vitest";
import { looksLikeResourceDump, sanitizeUploadError } from "./userErrors";

describe("userErrors", () => {
  it("does not leak CUDA allocator text", () => {
    const raw =
      "CUDA out of memory. Tried to allocate 2.00 GiB (GPU 0; 8.00 GiB total capacity; PyTorch allocator, PYTORCH_CUDA_ALLOC_CONF)";
    expect(looksLikeResourceDump(raw)).toBe(true);
    expect(sanitizeUploadError(raw, "paper.pdf")).toContain("Could not index paper.pdf");
    expect(sanitizeUploadError(raw, "paper.pdf")).not.toMatch(/CUDA|PyTorch|allocator/i);
  });

  it("leaves ordinary API messages unchanged", () => {
    expect(sanitizeUploadError("The file is not a valid PDF.", "x.pdf")).toBe(
      "The file is not a valid PDF.",
    );
  });
});
