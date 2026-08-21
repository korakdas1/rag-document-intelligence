import { describe, expect, it, vi } from "vitest";
import {
  desiredTurnScrollTop,
  maxPaneScrollTop,
  scrollPaneToTurn,
  spacerHeightToPinTurn,
  TURN_TOP_PAD,
  turnIsVisibleInPane,
} from "./conversationScroll";

function rect(top: number, height: number): DOMRect {
  return {
    x: 0,
    y: top,
    width: 400,
    height,
    top,
    left: 0,
    bottom: top + height,
    right: 400,
    toJSON() {
      return {};
    },
  };
}

function fakeEl(top: number, height: number, scrollTop = 0): HTMLElement {
  const el = document.createElement("div");
  vi.spyOn(el, "getBoundingClientRect").mockReturnValue(rect(top, height));
  Object.defineProperty(el, "scrollTop", { writable: true, value: scrollTop });
  Object.defineProperty(el, "clientHeight", { configurable: true, value: height });
  let scrollHeight = height;
  Object.defineProperty(el, "scrollHeight", {
    configurable: true,
    get: () => scrollHeight,
    set: (value: number) => {
      scrollHeight = value;
    },
  });
  el.scrollTo = vi.fn((arg?: ScrollToOptions | number, y?: number) => {
    const next = typeof arg === "object" && arg && "top" in arg ? Number(arg.top) : Number(y);
    const max = Math.max(0, el.scrollHeight - el.clientHeight);
    el.scrollTop = Math.max(0, Math.min(next, max));
  }) as HTMLElement["scrollTo"];
  return el;
}

function setScrollHeight(el: HTMLElement, value: number) {
  Object.defineProperty(el, "scrollHeight", { configurable: true, writable: true, value });
}

describe("conversationScroll", () => {
  it("detects a turn fully inside the pane", () => {
    const pane = fakeEl(0, 400);
    const turn = fakeEl(40, 80);
    expect(turnIsVisibleInPane(pane, turn)).toBe(true);
  });

  it("detects a turn above the pane", () => {
    const pane = fakeEl(200, 400);
    const turn = fakeEl(0, 80);
    expect(turnIsVisibleInPane(pane, turn)).toBe(false);
  });

  it("computes the scrollTop that places the turn near the top", () => {
    const pane = fakeEl(0, 400, 0);
    setScrollHeight(pane, 2000);
    const turn = fakeEl(800, 120);
    expect(desiredTurnScrollTop(pane, turn)).toBe(800 - TURN_TOP_PAD);
  });

  it("cannot place the last turn at the top without trailing space", () => {
    const pane = fakeEl(0, 400, 0);
    setScrollHeight(pane, 2000);
    const turn = fakeEl(1800, 120);
    const desired = desiredTurnScrollTop(pane, turn);
    expect(desired).toBe(1788);
    expect(maxPaneScrollTop(pane)).toBe(1600);
    expect(desired).toBeGreaterThan(maxPaneScrollTop(pane));
    scrollPaneToTurn(pane, turn, { behavior: "auto" });
    expect(pane.scrollTop).toBe(1600);
    expect(1800 - pane.scrollTop).toBe(200);
  });

  it("adds trailing space so the last turn can sit at the top pad", () => {
    const pane = fakeEl(0, 400, 0);
    setScrollHeight(pane, 2000);
    const turn = fakeEl(1800, 120);
    const spacer = spacerHeightToPinTurn(pane, turn, 0);
    expect(spacer).toBe(188);
    setScrollHeight(pane, 2000 + spacer);
    const turnAfter = fakeEl(1800, 120);
    expect(desiredTurnScrollTop(pane, turnAfter)).toBe(1788);
    expect(maxPaneScrollTop(pane)).toBe(1788);
    scrollPaneToTurn(pane, turnAfter, { behavior: "auto" });
    expect(pane.scrollTop).toBe(1788);
    expect(pane.scrollTo).toHaveBeenCalledWith({ top: 1788, behavior: "auto" });
  });

  it("uses auto scroll when the user prefers reduced motion", () => {
    const pane = fakeEl(0, 400, 0);
    setScrollHeight(pane, 2000);
    const turn = fakeEl(800, 120);
    const restore = window.matchMedia;
    window.matchMedia = ((query: string) =>
      ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addListener() {},
        removeListener() {},
        addEventListener() {},
        removeEventListener() {},
        dispatchEvent() {
          return false;
        },
      })) as typeof window.matchMedia;
    try {
      scrollPaneToTurn(pane, turn, { behavior: "smooth" });
      expect(pane.scrollTo).toHaveBeenCalledWith({ top: 800 - TURN_TOP_PAD, behavior: "auto" });
      expect(pane.scrollTop).toBe(800 - TURN_TOP_PAD);
    } finally {
      window.matchMedia = restore;
    }
  });

  it("requests smooth pane-local scrolling", () => {
    const pane = fakeEl(0, 400, 0);
    setScrollHeight(pane, 2000);
    const turn = fakeEl(800, 120);
    scrollPaneToTurn(pane, turn, { behavior: "smooth" });
    expect(pane.scrollTo).toHaveBeenCalledWith({
      top: 800 - TURN_TOP_PAD,
      behavior: "smooth",
    });
  });

  it("does not shrink an existing spacer when there is already enough room", () => {
    const pane = fakeEl(0, 400, 0);
    setScrollHeight(pane, 2400);
    const turn = fakeEl(200, 120);
    expect(spacerHeightToPinTurn(pane, turn, 400)).toBe(400);
  });

  it("does not keep growing the spacer when the pane cannot scroll", () => {
    const pane = fakeEl(0, 480, 0);
    setScrollHeight(pane, 200);
    const turn = fakeEl(24, 80);
    let height = 0;
    for (let i = 0; i < 50; i += 1) {
      const next = spacerHeightToPinTurn(pane, turn, height);
      if (next === height) {
        expect(i).toBeLessThan(3);
        expect(next).toBeLessThanOrEqual(480);
        return;
      }
      height = next;
    }
    throw new Error("spacer did not converge");
  });

  it("leaves the spacer unchanged when the turn is already at the reading pad", () => {
    const pane = fakeEl(0, 480, 0);
    setScrollHeight(pane, 200);
    const turn = fakeEl(TURN_TOP_PAD, 80);
    expect(spacerHeightToPinTurn(pane, turn, 0)).toBe(0);
  });
});
