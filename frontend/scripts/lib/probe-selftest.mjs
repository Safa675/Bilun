// Built-in page and checks for the visibility probes of lib/page-probes.mjs.
// Shared by `capture-screens.mjs --self-test` and by the vitest test
// (page-probes.test.mjs), so `npx vitest run` guards the probes whenever Chrome
// is installed. Every word below is a text marker: VIS_* must stay in the
// default-view text, HID_* must be dropped from it.
import { chromium } from "playwright";
import { installPageProbes } from "./page-probes.mjs";

export const SELF_TEST_SELECTOR = "#main-content";

const SELF_TEST_VISIBLE = [
  "VIS_PLAIN", "VIS_ZERO_WRAPPER", "VIS_CONTENTS", "VIS_INLINE", "VIS_OPEN_DETAILS",
  "VIS_PADDED_BOX", "VIS_ABS_IN_PADDING", "VIS_TRANSFORMED", "VIS_CLIPPATH_INSET",
];
// innerText still returns these (CSS collapsed them) - the probes must not.
const SELF_TEST_COLLAPSED = [
  "HID_HEIGHT0", "HID_MAXHEIGHT0", "HID_GRID0FR", "HID_OPACITY0", "HID_SRONLY", "HID_OFFSCREEN",
  // collapsed boxes that keep padding or a border: the box itself is tall, its content box is not
  "HID_PAD_MAXH0", "HID_PAD_TOP_H0", "HID_BORDER_ONLY", "HID_H1_PAD", "HID_PAD_BORDERBOX", "HID_GRID0FR_PADDED",
  // scaled or clipped to nothing
  "HID_SCALEY0", "HID_SCALEX0", "HID_CLIPPATH_INSET50", "HID_CLIPPATH_BOTTOM100",
];
// innerText already leaves these out.
const SELF_TEST_EXCLUDED = ["HID_DISPLAYNONE", "HID_ATTRIBUTE", "HID_VISIBILITY", "HID_CLOSED_DETAILS"];

export const SELF_TEST_HTML = `<!doctype html><html><body><main id="main-content">
  <div>VIS_PLAIN</div>
  <div style="height:0"><span>VIS_ZERO_WRAPPER</span></div>
  <div style="display:contents"><span>VIS_CONTENTS</span></div>
  <p>before <span>VIS_INLINE</span> after</p>
  <details open><summary>s</summary>VIS_OPEN_DETAILS</details>
  <div style="overflow:hidden;padding:12px;border:1px solid #000">VIS_PADDED_BOX</div>
  <div style="position:relative;overflow:hidden;padding:20px;height:80px"><span style="position:absolute;top:2px;left:2px">VIS_ABS_IN_PADDING</span></div>
  <div style="transform:translateX(8px) scale(0.9)">VIS_TRANSFORMED</div>
  <div style="clip-path:inset(4px)">VIS_CLIPPATH_INSET</div>
  <div data-case="height0" style="height:0;overflow:hidden">HID_HEIGHT0</div>
  <div style="max-height:0;overflow:hidden">HID_MAXHEIGHT0</div>
  <div style="display:grid;grid-template-rows:0fr"><div style="overflow:hidden;min-height:0">HID_GRID0FR</div></div>
  <div style="opacity:0">HID_OPACITY0</div>
  <span style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap">HID_SRONLY</span>
  <div style="position:absolute;left:-9999px">HID_OFFSCREEN</div>
  <div data-case="padded" style="max-height:0;overflow:hidden;padding:12px;border:1px solid #000">HID_PAD_MAXH0</div>
  <div style="height:0;overflow:hidden;padding-top:12px">HID_PAD_TOP_H0</div>
  <div style="height:0;overflow:hidden;border-bottom:3px solid #000">HID_BORDER_ONLY</div>
  <div style="height:1px;overflow:hidden;padding-bottom:4px">HID_H1_PAD</div>
  <div style="height:0;overflow:hidden;padding:16px;box-sizing:border-box">HID_PAD_BORDERBOX</div>
  <div style="display:grid;grid-template-rows:0fr"><div style="overflow:hidden;min-height:0;padding:10px">HID_GRID0FR_PADDED</div></div>
  <div style="transform:scaleY(0)">HID_SCALEY0</div>
  <div style="display:inline-block;transform:scaleX(0)">HID_SCALEX0</div>
  <div style="clip-path:inset(50%)">HID_CLIPPATH_INSET50</div>
  <div style="clip-path:inset(0 0 100% 0)">HID_CLIPPATH_BOTTOM100</div>
  <div style="display:none">HID_DISPLAYNONE</div>
  <div hidden>HID_ATTRIBUTE</div>
  <div style="visibility:hidden">HID_VISIBILITY</div>
  <details><summary>s</summary>HID_CLOSED_DETAILS</details>
</main></body></html>`;

// Whole-word match: a marker must not be found inside a longer one (HID_GRID0FR in HID_GRID0FR_PADDED).
const hasWord = (text, word) => new RegExp(`(?<![A-Za-z0-9_])${word}(?![A-Za-z0-9_])`).test(text);

const readScopes = (page) =>
  page.evaluate((selector) => [...document.querySelectorAll(selector)].map((s) => s.innerText).join("\n"), SELF_TEST_SELECTOR);
const readVisible = (page) => page.evaluate((selector) => window.__bilunCapture.visibleText(selector), SELF_TEST_SELECTOR);

/**
 * Runs the checks in a real Chrome. launchOptions: { channel } or { executablePath }.
 * Returns { problems, premises }: `problems` are defects of the probes; `premises` say that
 * this Chrome's innerText no longer behaves the way the probes assume (a note, not a defect).
 */
export async function runProbeSelfTest(launchOptions) {
  const browser = await chromium.launch({ headless: true, ...launchOptions });
  const problems = [];
  const premises = [];
  try {
    const context = await browser.newContext({ viewport: { width: 800, height: 600 } });
    await context.addInitScript(installPageProbes);
    const page = await context.newPage();
    await page.setContent(SELF_TEST_HTML);
    const before = await readScopes(page);
    const visible = await readVisible(page);
    const after = await readScopes(page);
    const restored = await page.evaluate(() => {
      const style = (selector) => {
        const el = document.querySelector(selector);
        return { display: el.style.getPropertyValue("display"), height: el.style.height, overflow: el.style.overflow, padding: el.style.padding };
      };
      return { height0: style('[data-case="height0"]'), padded: style('[data-case="padded"]') };
    });
    for (const word of SELF_TEST_VISIBLE) if (!hasWord(visible.text, word)) problems.push(`${word} is visible but the probe dropped it`);
    for (const word of [...SELF_TEST_COLLAPSED, ...SELF_TEST_EXCLUDED]) if (hasWord(visible.text, word)) problems.push(`${word} is hidden but the probe kept it`);
    for (const word of SELF_TEST_COLLAPSED) if (!hasWord(before, word)) premises.push(`innerText no longer includes ${word}, so the probe is not needed for it`);
    if (after !== before) problems.push("the page was not restored after the probe");
    if (restored.height0.display !== "" || restored.height0.height !== "0px" || restored.height0.overflow !== "hidden") {
      problems.push(`inline style was not restored (${JSON.stringify(restored.height0)})`);
    }
    if (restored.padded.display !== "" || restored.padded.padding !== "12px") problems.push(`padded inline style was not restored (${JSON.stringify(restored.padded)})`);
    if (visible.hiddenElements < SELF_TEST_COLLAPSED.length) problems.push(`only ${visible.hiddenElements} elements were reported hidden`);
  } finally {
    await browser.close();
  }
  return { problems, premises };
}
