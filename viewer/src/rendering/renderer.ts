import * as THREE from "three";

export function createRenderer(canvas: HTMLCanvasElement): THREE.WebGLRenderer {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.localClippingEnabled = true;

  canvas.addEventListener(
    "webglcontextlost",
    (event) => {
      event.preventDefault();
      const message = document.getElementById("viewer-error");
      if (message) {
        message.textContent =
          "WebGL context was lost. Reload the page to restore the 3D view.";
        message.style.display = "block";
      }
    },
    false,
  );

  return renderer;
}
