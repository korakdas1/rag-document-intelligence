import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {};
}

if (typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string) =>
    ({
      // Existing application tests exercise the full desktop workspace.
      // Shell tests override this with explicit media-query change events.
      matches: query === "(min-width: 1280px)" || query === "(min-width: 900px)",
      media: query,
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent() {
        return false;
      },
    }) as MediaQueryList;
}

afterEach(() => {
  cleanup();
});
