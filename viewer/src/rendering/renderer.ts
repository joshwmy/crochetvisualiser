import * as THREE from "three";

export function createRenderer(canvas: HTMLCanvasElement): THREE.WebGLRenderer {
  // alpha: presets with a null scene.background (the default soft_studio)
  // let the page's CSS stage gradient show behind the model.
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.9;
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

const SOFTWARE_RENDERER = /swiftshader|llvmpipe|softpipe|software|basic render driver/i;

/**
 * True when WebGL is running on a CPU rasteriser rather than a GPU — e.g.
 * headless Chromium (SwiftShader), VMs, or a blocklisted GPU driver.
 * Measured there on the 108-stitch example: ~930 ms/frame with the room
 * environment map and ply bump map, ~250 ms without, so App drops both on
 * software renderers. On real GPUs neither has a measurable cost.
 */
export function isSoftwareRenderer(renderer: THREE.WebGLRenderer): boolean {
  const gl = renderer.getContext();
  const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
  const name = debugInfo
    ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)
    : gl.getParameter(gl.RENDERER);
  return SOFTWARE_RENDERER.test(String(name ?? ""));
}
