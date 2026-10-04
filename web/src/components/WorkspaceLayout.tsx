import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Dialog } from "./ui/Dialog";

export type WorkspacePane = "documents" | "workspace" | "evidence";
// Keep these thresholds aligned with index.css. JS owns interaction/visibility;
// CSS owns sizing. No viewport dimensions are used as test geometry.
const WIDE = "(min-width: 1280px)";
const SPLIT = "(min-width: 900px)";
function subscribe(onChange: () => void) {
  const queries = [WIDE, SPLIT].map((query) => window.matchMedia?.(query));
  queries.forEach((query) => query?.addEventListener("change", onChange));
  return () => queries.forEach((query) => query?.removeEventListener("change", onChange));
}
function getMode() {
  if (!window.matchMedia || window.matchMedia(WIDE).matches) return "wide";
  return window.matchMedia(SPLIT).matches ? "split" : "mobile";
}

type Props = {
  pane: WorkspacePane;
  onPaneChange: (pane: WorkspacePane) => void;
  documents: ReactNode;
  children: ReactNode;
  evidence: ReactNode;
};

export function WorkspaceLayout({ pane, onPaneChange, documents, children, evidence }: Props) {
  const mode = useSyncExternalStore(subscribe, getMode);
  const [drawer, setDrawer] = useState(false);
  const drawerOpen = mode === "split" && drawer;
  // A stable portal destination keeps the library, its local menu state, and
  // scroll position alive when it moves between the shell and modal drawer.
  const [libraryHost] = useState(() => document.createElement("div"));
  libraryHost.className = "library-host";
  const libraryScrollTop = useRef(0);
  useLayoutEffect(() => {
    function rememberScroll(event: Event) {
      const target = event.target;
      if (target instanceof HTMLElement && target.matches(".pane-scroll") &&
        target.isConnected && !target.closest("[hidden]")) {
        libraryScrollTop.current = target.scrollTop;
      }
    }
    libraryHost.addEventListener("scroll", rememberScroll, true);
    return () => libraryHost.removeEventListener("scroll", rememberScroll, true);
  }, [libraryHost]);
  const moveLibrary = useCallback((node: HTMLDivElement | null) => {
    if (!node || libraryHost.parentElement === node) return;
    const scroll = libraryHost.querySelector<HTMLElement>(".pane-scroll");
    // Hidden/detached elements report zero in browsers. Retain the last visible
    // offset rather than overwriting it while the drawer is being torn down.
    if (scroll?.isConnected && !scroll.closest("[hidden]")) {
      libraryScrollTop.current = scroll.scrollTop;
    }
    node.append(libraryHost);
    if (scroll?.isConnected) scroll.scrollTop = libraryScrollTop.current;
  }, [libraryHost]);
  const inlineLibrary = useCallback((node: HTMLDivElement | null) => {
    if (!drawerOpen) moveLibrary(node);
  }, [drawerOpen, moveLibrary]);
  // Dialog attaches its portal in a child layout effect. Restore after that
  // attachment; setting scrollTop on a detached drawer is ignored by browsers.
  useLayoutEffect(() => {
    const scroll = libraryHost.querySelector<HTMLElement>(".pane-scroll");
    if (scroll?.isConnected && !scroll.closest("[hidden]")) {
      scroll.scrollTop = libraryScrollTop.current;
    }
  }, [drawerOpen, mode, pane, libraryHost]);
  useEffect(() => {
    if (mode !== "split") setDrawer(false);
  }, [mode]);

  return <>
    {mode === "split" && <nav className="workspace-nav" aria-label="Workspace tools">
      <button type="button" aria-haspopup="dialog" aria-expanded={drawerOpen}
        onClick={() => setDrawer(true)}>Documents</button>
      <span>Conversation <span aria-hidden="true">/</span> Sources</span>
    </nav>}
    {mode === "mobile" && <nav className="workspace-nav mobile-nav" aria-label="Sections">
      {([ ["documents", "Documents"], ["workspace", "Conversation"], ["evidence", "Sources"] ] as const)
        .map(([value, label]) => <button key={value} type="button" aria-pressed={pane === value}
          onClick={() => onPaneChange(value)}>{label}</button>)}
    </nav>}
    <div className={`layout layout-${mode}`}>
      <div className="library-slot" ref={inlineLibrary}
        hidden={mode === "split" || (mode === "mobile" && pane !== "documents")} />
      <div className="workspace-slot" hidden={mode === "mobile" && pane !== "workspace"}>{children}</div>
      <div className="evidence-slot" hidden={mode === "mobile" && pane !== "evidence"}>{evidence}</div>
    </div>
    {drawerOpen && <Dialog title="Documents" variant="drawer" dismissOnBackdrop
      backdropTestId="documents-backdrop" onClose={() => setDrawer(false)}>
      <button className="btn btn-quiet drawer-close" type="button" onClick={() => setDrawer(false)}>
        Close Documents
      </button>
      <div className="drawer-library" ref={moveLibrary} />
    </Dialog>}
    {createPortal(documents, libraryHost)}
  </>;
}
