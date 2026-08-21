const RESOURCE_DUMP =
  /cuda|cublas|cudnn|pytorch allocator|out of memory|std::bad_alloc|cannot allocate memory/i;

export function looksLikeResourceDump(message: string): boolean {
  return RESOURCE_DUMP.test(message);
}

export function sanitizeUploadError(message: string, filename?: string): string {
  const isResource =
    looksLikeResourceDump(message) ||
    message.startsWith("Could not index") ||
    message.includes("model memory was insufficient");
  if (!isResource) {
    return message;
  }
  const name = filename?.trim();
  if (name) {
    return (
      `Could not index ${name}: available model memory was insufficient. ` +
      "Try again after other processing finishes or free system/GPU memory."
    );
  }
  if (message.startsWith("Could not index") && !looksLikeResourceDump(message)) {
    return message;
  }
  return "Could not index this document because a local processing resource was unavailable.";
}
