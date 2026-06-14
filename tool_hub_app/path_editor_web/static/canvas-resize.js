export function installCanvasResizeSync({
  target,
  pathCanvas,
  ResizeObserverCtor = globalThis.ResizeObserver,
  windowObj = globalThis.window,
} = {}) {
  if (!target || !pathCanvas || typeof pathCanvas.resize !== "function") {
    return () => {};
  }

  const scheduleResize = () => {
    const requestFrame = windowObj?.requestAnimationFrame?.bind(windowObj);
    if (requestFrame) {
      requestFrame(() => pathCanvas.resize());
    } else {
      pathCanvas.resize();
    }
  };

  let observer = null;
  if (typeof ResizeObserverCtor === "function") {
    observer = new ResizeObserverCtor(scheduleResize);
    observer.observe(target);
  }

  windowObj?.addEventListener?.("resize", scheduleResize);

  return () => {
    observer?.disconnect?.();
    windowObj?.removeEventListener?.("resize", scheduleResize);
  };
}

