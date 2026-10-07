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
//
// What counts as hidden (each case has a line in probe-selftest.mjs, run by
// `capture-screens.mjs --self-test` and by vitest when Chrome is installed):
//   - display:none, visibility:hidden, opacity:0, content-visibility (checkVisibility);
//   - a box that clips (overflow other than visible) and has no room left in its CONTENT
//     box (width or height under 2 px after padding): padding or a border keeps the box
//     itself tall but shows none of its in-flow content (max-height:0 + padding is the
//     usual way a collapse leaves a sliver behind);
//   - a transform that scales a laid-out box to nothing (scaleY(0));
//   - a clip-path inset() that clips the whole box (inset(50%), inset(0 0 100% 0));
//   - a box left of or above the document origin (position:absolute;left:-9999px).
// Not detected: other clip-path shapes (circle(0), polygon()), color:transparent,
// text-indent:-9999px, content covered by another element.

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
    const clips = (cs.overflowX !== "visible" || cs.overflowY !== "visible") && cs.display !== "inline"; // overflow does not apply to inline boxes
    if (clips) {
      // clientWidth/clientHeight are the padding box (no border, no scrollbar, no transform): take the padding off
      const pad = (a, b) => (parseFloat(cs[a]) || 0) + (parseFloat(cs[b]) || 0);
      const contentWidth = el.clientWidth - pad("paddingLeft", "paddingRight");
      const contentHeight = el.clientHeight - pad("paddingTop", "paddingBottom");
      if (contentWidth < MIN_BOX || contentHeight < MIN_BOX) return true; // height:0, max-height:0, grid 0fr, sr-only, also with padding or border
    }
    if (typeof el.offsetWidth === "number") {
      // a laid-out box that a transform shrank to nothing: scaleY(0), scaleX(0)
      if (cs.transform !== "none" && ((el.offsetWidth >= MIN_BOX && r.width < MIN_BOX) || (el.offsetHeight >= MIN_BOX && r.height < MIN_BOX))) return true;
      // clip-path: inset(...) that leaves no area
      const inset = /^inset\(([^)]*)\)/.exec(cs.clipPath ?? "");
      if (inset) {
        const [top, right = top, bottom = top, left = right] = inset[1].split(/\s+round\s+/)[0].trim().split(/\s+/);
        const len = (value, basis) => (value.endsWith("%") ? (parseFloat(value) / 100) * basis : parseFloat(value) || 0);
        if (el.offsetWidth - len(left, el.offsetWidth) - len(right, el.offsetWidth) < MIN_BOX || el.offsetHeight - len(top, el.offsetHeight) - len(bottom, el.offsetHeight) < MIN_BOX) return true;
      }
    }
    if (r.right + window.scrollX < -OFFSCREEN || r.bottom + window.scrollY < -OFFSCREEN) return true; // left:-9999px, closed off-canvas drawer
    return false;
  }

  /** The elements a selector matches, minus those inside another match (a dialog inside #main-content is counted once). */
  function scopesOf(selector) {
    const all = [...document.querySelectorAll(selector)];
    return all.filter((scope) => !all.some((other) => other !== scope && other.contains(scope)));
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
    const scopes = scopesOf(selector);
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

  Object.defineProperty(window, "__bilunCapture", { value: { selfHidden, hiddenCheck, visibleText, scopesOf }, configurable: true });
}
