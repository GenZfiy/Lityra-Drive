// Browser proctoring hooks. Attaches integrity listeners, reports events to the
// Anti-Cheating service (best-effort), and calls onViolation so the exam runner
// can warn and auto-submit on threshold. Detections are advisory — the backend
// applies weighted scoring and the auto-submit decision.

// `block` (default true) = exam mode: also prevents right-click. Pass block:false
// on practice/learning surfaces so integrity is still *flagged* (visible to the
// student) without breaking normal use like copy/paste of code.
export function attachProctoring({ onViolation, block = true }) {
  const record = (type) => onViolation(type);

  const onVisibility = () => {
    if (document.hidden) record("tab_switch");
  };
  // NOTE: window "blur" (screen sleep / dim / OS notification) is intentionally
  // NOT flagged — it produced false positives when a device simply went idle.
  // Actual tab/app switching is still caught by visibilitychange above.
  const onContextMenu = (e) => {
    if (block) e.preventDefault();
    record("right_click");
  };
  const onCopy = () => record("copy");
  const onPaste = () => record("paste");
  const onFullscreen = () => {
    if (!document.fullscreenElement) record("fullscreen_exit");
  };
  const onBeforeUnload = () => record("page_refresh");

  document.addEventListener("visibilitychange", onVisibility);
  document.addEventListener("contextmenu", onContextMenu);
  document.addEventListener("copy", onCopy);
  document.addEventListener("paste", onPaste);
  document.addEventListener("fullscreenchange", onFullscreen);
  window.addEventListener("beforeunload", onBeforeUnload);

  return () => {
    document.removeEventListener("visibilitychange", onVisibility);
    document.removeEventListener("contextmenu", onContextMenu);
    document.removeEventListener("copy", onCopy);
    document.removeEventListener("paste", onPaste);
    document.removeEventListener("fullscreenchange", onFullscreen);
    window.removeEventListener("beforeunload", onBeforeUnload);
  };
}

// Human-readable labels for the proctor log.
export const SIGNAL_LABEL = {
  tab_switch: "Tab switch",
  window_blur: "Window lost focus",
  fullscreen_exit: "Exited fullscreen",
  right_click: "Right-click blocked",
  copy: "Copy detected",
  paste: "Paste detected",
  page_refresh: "Refresh attempt",
};
