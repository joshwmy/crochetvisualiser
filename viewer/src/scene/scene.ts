import * as THREE from "three";

export function createScene(): THREE.Scene {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x11151c);

  const hemisphere = new THREE.HemisphereLight(0xffffff, 0x444455, 1.2);
  scene.add(hemisphere);

  const key = new THREE.DirectionalLight(0xffffff, 1.5);
  key.position.set(5, 8, 6);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xaaccff, 0.4);
  fill.position.set(-6, 2, -4);
  scene.add(fill);

  const grid = new THREE.GridHelper(40, 40, 0x2a3040, 0x1c2028);
  grid.position.y = -20;
  scene.add(grid);

  const axes = new THREE.AxesHelper(3);
  scene.add(axes);

  return scene;
}
