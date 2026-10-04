// One background/scroll-lock owner for dialogs layered above a drawer. Only the
// top layer traps focus; removing any layer recomputes isolation from originals.
const layers: HTMLElement[] = [];
const background = new Map<Element, { inert: string | null; hidden: string | null }>();
let overflow = "";
let observer: MutationObserver | undefined;

function isolate() {
  const top = layers.at(-1);
  for (const child of document.body.children) {
    if (!background.has(child)) {
      background.set(child, { inert: child.getAttribute("inert"), hidden: child.getAttribute("aria-hidden") });
    }
    if (child === top) {
      child.removeAttribute("inert");
      child.removeAttribute("aria-hidden");
    } else {
      child.setAttribute("inert", "");
      child.setAttribute("aria-hidden", "true");
    }
  }
}

export function isTopModal(host: HTMLElement) {
  return layers.at(-1) === host;
}

export function canRestoreModalFocus(target: HTMLElement) {
  return !layers.length || layers.at(-1)!.contains(target);
}

export function registerModal(host: HTMLElement) {
  if (!layers.length) {
    overflow = document.body.style.overflow;
    observer = new MutationObserver(isolate);
    observer.observe(document.body, { childList: true });
    document.body.style.overflow = "hidden";
  }
  layers.push(host);
  isolate();
  return () => {
    layers.splice(layers.indexOf(host), 1);
    if (layers.length) {
      isolate();
    } else {
      observer?.disconnect();
      for (const [element, saved] of background) {
        if (saved.inert === null) element.removeAttribute("inert");
        else element.setAttribute("inert", saved.inert);
        if (saved.hidden === null) element.removeAttribute("aria-hidden");
        else element.setAttribute("aria-hidden", saved.hidden);
      }
      background.clear();
      document.body.style.overflow = overflow;
    }
  };
}
