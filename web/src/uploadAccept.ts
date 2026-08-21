/** Client-side upload accept list — mirrors the Add documents picker and API suffixes. */

export const SUPPORTED_UPLOAD_SUFFIXES = [".pdf", ".txt", ".md", ".markdown"] as const;

export const UNSUPPORTED_UPLOAD_MESSAGE =
  "Unsupported file type. Add a PDF, Markdown, or text file.";

export function fileSuffix(filename: string): string {
  const trimmed = filename.trim();
  const dot = trimmed.lastIndexOf(".");
  if (dot <= 0 || dot === trimmed.length - 1) {
    return "";
  }
  return trimmed.slice(dot).toLowerCase();
}

export function isSupportedUploadFile(file: File): boolean {
  return (SUPPORTED_UPLOAD_SUFFIXES as readonly string[]).includes(fileSuffix(file.name));
}

export function dataTransferHasFiles(dataTransfer: DataTransfer | null): boolean {
  if (!dataTransfer) {
    return false;
  }
  const types = dataTransfer.types;
  if (!types) {
    return false;
  }
  if (typeof types.includes === "function") {
    return types.includes("Files") || types.includes("application/x-moz-file");
  }
  if (typeof (types as unknown as { contains?: (value: string) => boolean }).contains === "function") {
    return (types as unknown as { contains: (value: string) => boolean }).contains("Files");
  }
  return Array.from(types as unknown as string[]).includes("Files");
}

export type FileDragKind = "files" | "unknown" | "not-files";

export function classifyFileDrag(dataTransfer: DataTransfer | null): FileDragKind {
  if (!dataTransfer) {
    return "not-files";
  }
  if (dataTransferHasFiles(dataTransfer)) {
    return "files";
  }
  const items = dataTransfer.items;
  if (items && items.length > 0) {
    for (let index = 0; index < items.length; index += 1) {
      if (items[index]?.kind === "file") {
        return "files";
      }
    }
    return "not-files";
  }
  const types = dataTransfer.types;
  if (!types || types.length === 0) {
    return "unknown";
  }
  return "not-files";
}

export type RejectedUpload = {
  filename: string;
  reason: string;
};

export function partitionUploadFiles(files: File[]): {
  accepted: File[];
  rejected: RejectedUpload[];
} {
  const accepted: File[] = [];
  const rejected: RejectedUpload[] = [];
  for (const file of files) {
    if (isSupportedUploadFile(file)) {
      accepted.push(file);
    } else {
      rejected.push({ filename: file.name || "file", reason: UNSUPPORTED_UPLOAD_MESSAGE });
    }
  }
  return { accepted, rejected };
}

export function formatRejectedUploads(rejected: RejectedUpload[]): string {
  return rejected.map((item) => `${item.filename}: ${item.reason}`).join(" ");
}

export function resolveDroppedFiles(files: File[]): {
  accepted: File[];
  rejected: RejectedUpload[];
  error?: string;
} {
  if (files.length === 0) {
    return { accepted: [], rejected: [], error: UNSUPPORTED_UPLOAD_MESSAGE };
  }
  const partitioned = partitionUploadFiles(files);
  if (partitioned.accepted.length === 0) {
    const error =
      partitioned.rejected.length === 1
        ? partitioned.rejected[0].reason
        : formatRejectedUploads(partitioned.rejected) || UNSUPPORTED_UPLOAD_MESSAGE;
    return { ...partitioned, error };
  }
  return partitioned;
}
