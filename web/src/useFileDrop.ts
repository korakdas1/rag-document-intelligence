import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type DragEvent as ReactDragEvent,
} from "react";
import { classifyFileDrag } from "./uploadAccept";

type DropBind = {
  ref: (node: HTMLElement | null) => void;
  onDragEnter: (event: ReactDragEvent) => void;
  onDragOver: (event: ReactDragEvent) => void;
  onDragLeave: (event: ReactDragEvent) => void;
  onDrop: (event: ReactDragEvent) => void;
};

type DragTraceRow = {
  t: number;
  ev: string;
  target: string;
  currentTarget: string;
  related: string;
  types: string;
  kind: string;
  dropActive: boolean;
  dragDepth: number;
  dropLock: boolean;
  pendingReset: boolean;
  uploadEnabled: boolean;
};

function nodeName(value: EventTarget | null): string {
  if (!value) {
    return "null";
  }
  if (value === window) {
    return "window";
  }
  if (value === document) {
    return "document";
  }
  if (value instanceof HTMLElement) {
    return `${value.tagName.toLowerCase()}${value.id ? `#${value.id}` : ""}${
      value.className ? `.${String(value.className).split(" ").slice(0, 2).join(".")}` : ""
    }`;
  }
  return value.constructor?.name ?? typeof value;
}

function typesOf(dt: DataTransfer | null | undefined): string {
  if (!dt?.types) {
    return "";
  }
  try {
    return Array.from(dt.types).join(",");
  } catch {
    return String(dt.types);
  }
}

function dragTraceEnabled(): boolean {
  try {
    return new URLSearchParams(window.location.search).has("dragTrace");
  } catch {
    return false;
  }
}

function isNodeInside(root: Node | null, node: EventTarget | null): boolean {
  return Boolean(root && node instanceof Node && root.contains(node));
}

export function useFileDrop(onFiles: (files: File[]) => void, enabled = true): {
  dropActive: boolean;
  dropBind: DropBind;
} {
  const [dropActive, setDropActive] = useState(false);
  const dropActiveRef = useRef(false);
  const enabledRef = useRef(enabled);
  const onFilesRef = useRef(onFiles);
  const rootRef = useRef<HTMLElement | null>(null);
  const resetEpochRef = useRef(0);
  const dropLockRef = useRef(false);
  const dragDepthRef = useRef(0);
  const traceRef = useRef<DragTraceRow[]>([]);
  enabledRef.current = enabled;
  onFilesRef.current = onFiles;

  const snapshot = useCallback(
    (eventName: string, event?: DragEvent | ReactDragEvent) => {
      if (!dragTraceEnabled()) {
        return;
      }
      const row: DragTraceRow = {
        t: Date.now(),
        ev: eventName,
        target: nodeName(event?.target ?? null),
        currentTarget: nodeName(event?.currentTarget ?? null),
        related: nodeName(event && "relatedTarget" in event ? event.relatedTarget : null),
        types: typesOf(event?.dataTransfer),
        kind: classifyFileDrag(event?.dataTransfer ?? null),
        dropActive: dropActiveRef.current,
        dragDepth: dragDepthRef.current,
        dropLock: dropLockRef.current,
        pendingReset: false,
        uploadEnabled: enabledRef.current,
      };
      const next = [...traceRef.current, row].slice(-40);
      traceRef.current = next;
      (window as unknown as { __RA_DRAG_TRACE?: DragTraceRow[] }).__RA_DRAG_TRACE = next;
      console.debug("[drag]", row);
    },
    [],
  );

  const resetVisual = useCallback(() => {
    resetEpochRef.current += 1;
    dropActiveRef.current = false;
    dragDepthRef.current = 0;
    setDropActive(false);
    snapshot("reset:visual");
  }, [snapshot]);

  const reset = useCallback(() => {
    resetVisual();
    dropLockRef.current = false;
    snapshot("reset:all");
  }, [resetVisual, snapshot]);

  const activate = useCallback(() => {
    resetEpochRef.current += 1;
    dropActiveRef.current = true;
    setDropActive(true);
  }, []);

  const cancelPendingReset = useCallback(() => {
    resetEpochRef.current += 1;
  }, []);

  const scheduleReset = useCallback(() => {
    const epoch = ++resetEpochRef.current;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (epoch === resetEpochRef.current) {
          dropActiveRef.current = false;
          dragDepthRef.current = 0;
          dropLockRef.current = false;
          setDropActive(false);
          snapshot("reset:raf");
        }
      });
    });
  }, [snapshot]);

  const setRoot = useCallback((node: HTMLElement | null) => {
    rootRef.current = node;
  }, []);

  const emitFiles = useCallback((files: File[]) => {
    if (!enabledRef.current || dropLockRef.current) {
      snapshot("emit:blocked");
      return;
    }
    dropLockRef.current = true;
    queueMicrotask(() => {
      dropLockRef.current = false;
    });
    onFilesRef.current(files);
  }, [snapshot]);

  const onDragEnter = useCallback(
    (event: ReactDragEvent) => {
      event.preventDefault();
      snapshot("shell:dragenter", event);
      if (!enabledRef.current) {
        return;
      }
      const kind = classifyFileDrag(event.dataTransfer);
      if (kind === "not-files") {
        return;
      }
      if (kind === "files" && isNodeInside(event.currentTarget, event.relatedTarget)) {
        cancelPendingReset();
        return;
      }
      if (kind === "files") {
        activate();
      }
    },
    [activate, cancelPendingReset, snapshot],
  );

  const onDragOver = useCallback(
    (event: ReactDragEvent) => {
      event.preventDefault();
      const kind = classifyFileDrag(event.dataTransfer);
      if (!enabledRef.current || kind === "not-files") {
        return;
      }
      event.dataTransfer.dropEffect = "copy";
      if (kind === "files") {
        if (dropActiveRef.current) {
          cancelPendingReset();
        } else {
          activate();
        }
      }
    },
    [activate, cancelPendingReset],
  );

  const onDragLeave = useCallback(
    (event: ReactDragEvent) => {
      if (!dropActiveRef.current) {
        return;
      }
      event.preventDefault();
      snapshot("shell:dragleave", event);
      const current = event.currentTarget as HTMLElement;
      if (isNodeInside(current, event.relatedTarget)) {
        return;
      }
      const nestedLeave =
        event.target instanceof Node &&
        event.target !== current &&
        current.contains(event.target);
      if (nestedLeave) {
        scheduleReset();
        return;
      }
      reset();
    },
    [reset, scheduleReset, snapshot],
  );

  const onDrop = useCallback(
    (event: ReactDragEvent) => {
      const kind = classifyFileDrag(event.dataTransfer);
      if (kind === "not-files" && !dropActiveRef.current) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      snapshot("shell:drop", event);
      resetVisual();
      emitFiles(Array.from(event.dataTransfer.files ?? []));
    },
    [emitFiles, resetVisual, snapshot],
  );

  useEffect(() => {
    if (!enabled) {
      reset();
    }
  }, [enabled, reset]);

  useEffect(() => {
    function onWindowDragEnter(event: DragEvent) {
      event.preventDefault();
      snapshot("window:dragenter", event);
      const kind = classifyFileDrag(event.dataTransfer);
      if (kind === "not-files" && !dropActiveRef.current) {
        return;
      }
      dragDepthRef.current += 1;
      if (kind === "files" && enabledRef.current) {
        activate();
      }
    }

    function onWindowDragOver(event: DragEvent) {
      // Chrome/Linux OS file drags often omit types on the first dragover
      // after a cancelled gesture. Skipping preventDefault here makes the
      // browser stop delivering the rest of that drag to the page.
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "copy";
      }
      const kind = classifyFileDrag(event.dataTransfer);
      if (kind === "not-files" && !dropActiveRef.current) {
        return;
      }
      if (!enabledRef.current) {
        return;
      }
      if (kind === "files") {
        if (dropActiveRef.current) {
          cancelPendingReset();
        } else {
          activate();
        }
      } else if (dropActiveRef.current) {
        cancelPendingReset();
      }
    }

    function onWindowDragLeave(event: DragEvent) {
      snapshot("window:dragleave", event);
      if (dragDepthRef.current > 0) {
        dragDepthRef.current -= 1;
        if (dragDepthRef.current <= 0) {
          reset();
        }
      }
    }

    function resetIfDragCancelled() {
      if (dropActiveRef.current || dragDepthRef.current > 0 || dropLockRef.current) {
        snapshot("cancel");
        reset();
      }
    }

    function onDocumentDragLeave(event: DragEvent) {
      snapshot("document:dragleave", event);
      if (!dropActiveRef.current) {
        return;
      }
      const root = rootRef.current;
      const target = event.target;
      if (
        target === document ||
        target === document.documentElement ||
        target === document.body
      ) {
        reset();
        return;
      }
      if (root && target instanceof Node && root.contains(target)) {
        if (event.relatedTarget == null) {
          scheduleReset();
        }
        return;
      }
      scheduleReset();
    }

    function onWindowDrop(event: DragEvent) {
      const kind = classifyFileDrag(event.dataTransfer);
      if (kind === "not-files" && !dropActiveRef.current) {
        return;
      }
      event.preventDefault();
      snapshot("window:drop", event);
      const root = rootRef.current;
      if (root && event.target instanceof Node && root.contains(event.target)) {
        return;
      }
      resetVisual();
      emitFiles(Array.from(event.dataTransfer?.files ?? []));
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        resetIfDragCancelled();
      }
    }

    function onFocus() {
      snapshot("window:focus");
    }

    function onDocMouseLeave(event: MouseEvent) {
      snapshot("document:mouseleave");
      if (event.relatedTarget == null) {
        resetIfDragCancelled();
      }
    }

    window.addEventListener("dragenter", onWindowDragEnter, true);
    window.addEventListener("dragover", onWindowDragOver, true);
    window.addEventListener("dragleave", onWindowDragLeave, true);
    window.addEventListener("drop", onWindowDrop);
    window.addEventListener("blur", resetIfDragCancelled);
    window.addEventListener("focus", onFocus);
    window.addEventListener("dragend", resetIfDragCancelled);
    document.addEventListener("dragleave", onDocumentDragLeave);
    document.addEventListener("visibilitychange", resetIfDragCancelled);
    document.documentElement.addEventListener("mouseleave", onDocMouseLeave);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("dragenter", onWindowDragEnter, true);
      window.removeEventListener("dragover", onWindowDragOver, true);
      window.removeEventListener("dragleave", onWindowDragLeave, true);
      window.removeEventListener("drop", onWindowDrop);
      window.removeEventListener("blur", resetIfDragCancelled);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("dragend", resetIfDragCancelled);
      document.removeEventListener("dragleave", onDocumentDragLeave);
      document.removeEventListener("visibilitychange", resetIfDragCancelled);
      document.documentElement.removeEventListener("mouseleave", onDocMouseLeave);
      window.removeEventListener("keydown", onKeyDown);
      reset();
    };
  }, [activate, cancelPendingReset, emitFiles, reset, resetVisual, scheduleReset, snapshot]);

  return {
    dropActive,
    dropBind: {
      ref: setRoot,
      onDragEnter,
      onDragOver,
      onDragLeave,
      onDrop,
    },
  };
}
