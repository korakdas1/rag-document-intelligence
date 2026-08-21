/** Scroll a conversation turn inside the chat pane — never window.scrollTo. */

export const TURN_TOP_PAD = 12;

export function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
}

export function resolveScrollBehavior(requested: ScrollBehavior = "auto"): ScrollBehavior {
  return prefersReducedMotion() ? "auto" : requested;
}

export function turnIsVisibleInPane(pane: HTMLElement, turn: HTMLElement): boolean {
  const paneRect = pane.getBoundingClientRect();
  const turnRect = turn.getBoundingClientRect();
  return turnRect.top >= paneRect.top - 1 && turnRect.bottom <= paneRect.bottom + 1;
}

export function turnOffsetFromPaneTop(pane: HTMLElement, turn: HTMLElement): number {
  const paneRect = pane.getBoundingClientRect();
  const turnRect = turn.getBoundingClientRect();
  return turnRect.top - paneRect.top;
}

export function desiredTurnScrollTop(
  pane: HTMLElement,
  turn: HTMLElement,
  pad = TURN_TOP_PAD,
): number {
  return pane.scrollTop + turnOffsetFromPaneTop(pane, turn) - pad;
}

export function maxPaneScrollTop(pane: HTMLElement): number {
  return Math.max(0, pane.scrollHeight - pane.clientHeight);
}

export function spacerHeightToPinTurn(
  pane: HTMLElement,
  turn: HTMLElement,
  currentSpacerHeight: number,
  pad = TURN_TOP_PAD,
): number {
  const offset = turnOffsetFromPaneTop(pane, turn);
  if (!Number.isFinite(offset) || offset <= pad + 1) {
    return currentSpacerHeight;
  }
  const desired = pane.scrollTop + offset - pad;
  const maxScroll = maxPaneScrollTop(pane);
  if (!Number.isFinite(desired) || !Number.isFinite(maxScroll)) {
    return currentSpacerHeight;
  }
  const shortfall = desired - maxScroll;
  if (shortfall <= 0) {
    return currentSpacerHeight;
  }
  // A trailing spacer only helps once the pane can scroll. If it still cannot,
  // further setState growth never converges and hits React's max update depth.
  if (maxScroll <= 0) {
    if (currentSpacerHeight > 0) {
      return currentSpacerHeight;
    }
    const viewport = Math.max(0, pane.clientHeight);
    return Math.min(
      Math.ceil(shortfall + viewport),
      Math.max(viewport, Math.ceil(shortfall)),
    );
  }
  const next = currentSpacerHeight + Math.ceil(shortfall);
  return Number.isFinite(next) ? next : currentSpacerHeight;
}

export function scrollPaneToTurn(
  pane: HTMLElement,
  turn: HTMLElement,
  options?: { behavior?: ScrollBehavior; pad?: number },
): number {
  const top = Math.max(
    0,
    Math.min(desiredTurnScrollTop(pane, turn, options?.pad ?? TURN_TOP_PAD), maxPaneScrollTop(pane)),
  );
  if (!Number.isFinite(top)) {
    return pane.scrollTop;
  }
  const behavior = resolveScrollBehavior(options?.behavior ?? "auto");
  if (typeof pane.scrollTo === "function") {
    pane.scrollTo({ top, behavior });
  }
  // Immediate assignment: reduced-motion, auto, and tests (jsdom does not animate).
  if (behavior === "auto" || Boolean(import.meta.env.VITEST)) {
    pane.scrollTop = top;
  }
  return top;
}
