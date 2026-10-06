// In-page helpers for capture-screens.mjs. installPageProbes() is serialised by
// Playwright (context.addInitScript), so it must stay self-contained: no imports
// and no references to anything outside the function.
//
// Why this exists: element.innerText excludes display:none, [hidden],
// visibility:hidden and a closed <details>, but it INCLUDES text in a box that
// CSS collapsed with height:0 / max-height:0 + overflow:hidden, grid-template-rows:0fr,
// opacity:0, a clipped 1px "sr-only" box or position:absolute;left:-9999px
// (measured in Chrome 154). A section collapsed that way would still count as
// "visible" and could hide uncertainty wording unnoticed. These probes decide
// visibility from the laid-out boxes instead.

export function installPageProbes() {
  const MIN_BOX = 2; // px: a clipping box thinner than this shows nothing
  const OFFSCREEN = 1; // px tolerance for "left of / above the document origin"

  /** True when the element itself (not an ancestor) renders nothing a person could see. */
  function selfHidden(el) {
    const cs = getComputedStyle(el);
    if (cs.display === "contents") return false; // no box of its own; its children decide
    if (cs.display === "none") return true;
    if (typeof el.checkVisibility === "function" && !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return true;
    const r = el.getBoundingClientRect();
    const clips = cs.overflowX !== "visible" || cs.overflowY !== "visible";
    if (clips && (r.width < MIN_BOX || r.height < MIN_BOX)) return true; // height:0, max-height:0, grid 0fr, sr-only
    if (r.right + window.scrollX < -OFFSCREEN || r.bottom + window.scrollY < -OFFSCREEN) return true; // left:-9999px, closed off-canvas drawer
    return false;
  }

  /** (el) => true when the element or any ancestor is hidden. Cached for one pass; call it again after a layout change. */
  function hiddenCheck() {
    const cache = new Map();
    const check = (el) => {
      if (!el) return false;
      if (cache.has(el)) return cache.get(el);
      const result = selfHidden(el) || check(el.parentElement);
      cache.set(el, result);
      return result;
    };
    return check;
  }

  /** innerText of every scope with all layout-hidden elements taken out; the page is restored afterwards. */
  function visibleText(selector) {
    const scopes = [...document.querySelectorAll(selector)];
    const hidden = [];
    const covered = new Set();
    for (const scope of scopes) {
      for (const el of scope.querySelectorAll("*")) {
        const parent = el.parentElement;
        if (parent && covered.has(parent)) {
          covered.add(el);
          continue;
        }
        if (selfHidden(el)) {
          hidden.push(el);
          covered.add(el);
        }
      }
    }
    const saved = [];
    try {
      for (const el of hidden) {
        if (!el.style) continue;
        saved.push([el, el.style.getPropertyValue("display"), el.style.getPropertyPriority("display")]);
        el.style.setProperty("display", "none", "important");
      }
      return { text: scopes.map((scope) => scope.innerText).join("\n"), hiddenElements: hidden.length };
    } finally {
      for (const [el, value, priority] of saved.reverse()) {
        if (value) el.style.setProperty("display", value, priority);
        else el.style.removeProperty("display");
      }
    }
  }

  Object.defineProperty(window, "__bilunCapture", { value: { selfHidden, hiddenCheck, visibleText }, configurable: true });
}
