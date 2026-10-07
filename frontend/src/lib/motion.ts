import { flushSync } from "react-dom";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function motionScrollBehavior(): ScrollBehavior {
  return prefersReducedMotion() ? "auto" : "smooth";
}

let billTransitionId = 0;
const billTransitions = new WeakMap<HTMLElement, {
  name: string;
  previousName: string;
  transition?: ViewTransition;
}>();

export function runBillCrossfade(root: HTMLElement | null, update: () => void, animate = true): void {
  if (!root || !animate || prefersReducedMotion() || typeof document === "undefined" ||
    typeof document.startViewTransition !== "function") {
    if (root) {
      const previous = billTransitions.get(root);
      billTransitions.delete(root);
      if (previous && root.style.viewTransitionName === previous.name) {
        root.style.viewTransitionName = previous.previousName;
      }
      previous?.transition?.skipTransition();
    }
    update();
    return;
  }

  const previous = billTransitions.get(root);
  previous?.transition?.skipTransition();
  const previousName = previous?.previousName ?? root.style.viewTransitionName;
  const name = `bilun-bill-${++billTransitionId}`;
  const current = { name, previousName, transition: undefined as ViewTransition | undefined };
  billTransitions.set(root, current);
  root.style.viewTransitionName = name;
  const owner = root.dataset?.patientId;
  const wasConnected = root.isConnected;
  let updated = false;
  const restore = () => {
    if (billTransitions.get(root) !== current) return;
    if (root.style.viewTransitionName === name) root.style.viewTransitionName = previousName;
    billTransitions.delete(root);
  };

  try {
    // Snapshot the complete owning pane, including its old claim label. The live
    // render still uses matchingBillReport; no old report is copied or deferred.
    const transition = document.startViewTransition(() => {
      updated = true;
      if (billTransitions.get(root) !== current) return;
      if (root.dataset?.patientId !== owner || (wasConnected && !root.isConnected)) return;
      flushSync(update);
    });
    current.transition = transition;
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onPreferenceChange = () => {
      if (preference.matches) transition.skipTransition();
    };
    preference.addEventListener("change", onPreferenceChange);
    void transition.finished.catch(() => undefined).finally(() => {
      preference.removeEventListener("change", onPreferenceChange);
      restore();
    });
  } catch {
    restore();
    if (!updated) update();
  }
}
