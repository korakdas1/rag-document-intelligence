import { useId, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

type DialogProps = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  initialFocusRef?: RefObject<HTMLElement | null>;
  selectInitialText?: boolean;
  busy?: boolean;
  dismissOnBackdrop?: boolean;
  testId?: string;
  backdropTestId?: string;
};

const FOCUSABLE = 'button, input:not([type="hidden"]), select, textarea, a[href], summary, [tabindex], [contenteditable="true"]';

function available(element: HTMLElement): boolean {
  if (!element.isConnected || element.matches(":disabled") ||
    element.closest('[inert], [hidden], [aria-hidden="true"], .visually-hidden')) {
    return false;
  }
  for (let node: HTMLElement | null = element; node; node = node.parentElement) {
    const style = getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") {
      return false;
    }
    if (node.parentElement instanceof HTMLDetailsElement && !node.parentElement.open && node.tagName !== "SUMMARY") {
      return false;
    }
  }
  return true;
}

function tabStops(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE))
    .filter((element) => element.tabIndex >= 0 && available(element))
    .sort((a, b) => (a.tabIndex || Infinity) - (b.tabIndex || Infinity));
}

/** Render only while open. The surviving opener is restored on unmount; if it
 * disappears or stays disabled, focus its owning landmark, then a page control.
 * The landmark survives an asynchronous list refresh (individual rows may not).
 * Menu actions focus their persistent menu trigger before opening a dialog.
 */
export function Dialog({
  title, onClose, children, initialFocusRef, selectInitialText = false,
  busy = false, dismissOnBackdrop = false, testId, backdropTestId,
}: DialogProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const [host] = useState(() => document.createElement("div"));
  const mounted = useRef(false);
  const latest = useRef({ onClose, busy, initialFocusRef, selectInitialText });
  latest.current = { onClose, busy, initialFocusRef, selectInitialText };

  useLayoutEffect(() => {
    mounted.current = true;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const landmark = opener?.closest<HTMLElement>('aside, main, nav, header, [role="region"]');
    document.body.append(host);
    const panel = panelRef.current!;
    let lastFocused: HTMLElement | null = null;
    const background = new Map<Element, { inert: string | null; hidden: string | null }>();
    const overflow = document.body.style.overflow;

    function focusInside() {
      const preferred = lastFocused ?? latest.current.initialFocusRef?.current;
      const target = preferred && panel.contains(preferred) && available(preferred)
        ? preferred : tabStops(panel)[0] ?? panel;
      target.focus();
    }

    function isolateBackground() {
      for (const child of document.body.children) {
        if (child === host || background.has(child)) continue;
        background.set(child, { inert: child.getAttribute("inert"), hidden: child.getAttribute("aria-hidden") });
        child.setAttribute("inert", "");
        child.setAttribute("aria-hidden", "true");
      }
    }

    function containFocus(event: FocusEvent) {
      if (event.target instanceof HTMLElement && panel.contains(event.target)) {
        lastFocused = event.target;
      } else {
        focusInside();
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!latest.current.busy) latest.current.onClose();
      } else if (event.key === "Tab") {
        event.preventDefault();
        event.stopImmediatePropagation();
        const stops = tabStops(panel);
        const index = stops.indexOf(document.activeElement as HTMLElement);
        const next = event.shiftKey
          ? (index <= 0 ? stops.length - 1 : index - 1)
          : (index + 1) % stops.length;
        (stops[next] ?? panel).focus();
      }
    }

    document.addEventListener("focusin", containFocus, true);
    document.addEventListener("keydown", onKeyDown, true);
    focusInside();
    if (latest.current.selectInitialText && document.activeElement instanceof HTMLInputElement) {
      document.activeElement.select();
    }
    isolateBackground();
    document.body.style.overflow = "hidden";

    // Busy updates can disable the focused button. Keep focus on the panel if
    // no controls remain, and isolate siblings mounted while the modal is open.
    const observer = new MutationObserver(() => {
      isolateBackground();
      const active = document.activeElement;
      if (!(active instanceof HTMLElement) || !panel.contains(active) || !available(active)) {
        lastFocused = null;
        focusInside();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, attributes: true,
      attributeFilter: ["disabled", "hidden", "style", "class", "tabindex", "open"] });

    return () => {
      mounted.current = false;
      observer.disconnect();
      document.removeEventListener("focusin", containFocus, true);
      document.removeEventListener("keydown", onKeyDown, true);
      for (const [element, saved] of background) {
        if (saved.inert === null) element.removeAttribute("inert");
        else element.setAttribute("inert", saved.inert);
        if (saved.hidden === null) element.removeAttribute("aria-hidden");
        else element.setAttribute("aria-hidden", saved.hidden);
      }
      document.body.style.overflow = overflow;
      host.remove();
      // Wait for the closing render to remove deleted triggers / re-enable
      // busy controls. StrictMode's effect replay must not steal initial focus.
      queueMicrotask(() => {
        if (mounted.current || document.querySelector('[role="dialog"][aria-modal="true"]')) return;
        if (opener && opener.matches(FOCUSABLE) && available(opener)) {
          opener.focus();
        } else if (landmark && available(landmark)) {
          const previous = landmark.getAttribute("tabindex");
          landmark.tabIndex = -1;
          landmark.focus();
          // Removing tabindex immediately blurs a non-focusable landmark in
          // browsers. Restore its original attribute only after focus leaves.
          landmark.addEventListener("blur", () => {
            if (previous === null) landmark.removeAttribute("tabindex");
            else landmark.setAttribute("tabindex", previous);
          }, { once: true });
        } else {
          const target = tabStops(document.body)[0];
          target?.focus();
        }
      });
    };
  }, [host]);

  return createPortal(
    <div className="dialog-backdrop" data-testid={backdropTestId}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          // Otherwise the pointer's default focus action can overwrite focus
          // restoration after the closing render and leave focus on body.
          event.preventDefault();
          if (dismissOnBackdrop && !busy) onClose();
        }
      }}>
      <div ref={panelRef} className="dialog" role="dialog" aria-modal="true"
        aria-labelledby={titleId} aria-busy={busy} tabIndex={-1} data-testid={testId}>
        <h3 id={titleId}>{title}</h3>
        {children}
      </div>
    </div>, host,
  );
}
