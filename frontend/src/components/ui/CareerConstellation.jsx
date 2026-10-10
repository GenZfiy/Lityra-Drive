import { useEffect, useRef } from "react";
import * as THREE from "three";

const SKILL_POINTS = [
  [-1.45, 0.15, 0.05],
  [-0.65, 0.85, -0.1],
  [0.05, 0.1, 0.15],
  [0.72, 0.8, 0.05],
  [1.42, 0.1, -0.1],
  [-0.58, -0.72, 0.08],
  [0.66, -0.68, 0.15],
];

const PATHS = [
  [0, 1, 2, 3, 4],
  [0, 5, 2, 6, 4],
  [1, 3, 6],
  [5, 6],
];

export function CareerConstellation({ className = "", mode = "full" }) {
  const hostRef = useRef(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;
    if ((mode === "ambient" || mode === "journey") && (window.matchMedia("(max-width: 700px)").matches || (navigator.deviceMemory && navigator.deviceMemory <= 2) || navigator.connection?.saveData)) return undefined;

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
    } catch {
      return undefined;
    }
    host.classList.add("has-webgl");

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 40);
    camera.position.set(0, 0, 6.4);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.setAttribute("aria-hidden", "true");
    renderer.domElement.className = "career-constellation-canvas";
    host.appendChild(renderer.domElement);

    const pathway = new THREE.Group();
    // The hero canvas sits behind a product preview card; scale its orbit so
    // the nodes and gold ring frame the card instead of disappearing beneath it.
    pathway.scale.setScalar(mode === "ambient" ? 1 : 1.4);
    scene.add(pathway);

    const coreMaterial = new THREE.MeshStandardMaterial({
      color: 0x8bc9ed,
      emissive: 0x174c78,
      emissiveIntensity: 0.46,
      metalness: 0.18,
      roughness: 0.28,
    });
    const accentMaterial = new THREE.MeshStandardMaterial({
      color: 0xe4c27a,
      emissive: 0x8f682b,
      emissiveIntensity: 0.34,
      metalness: 0.12,
      roughness: 0.34,
    });
    const nodeGeometry = new THREE.IcosahedronGeometry(0.115, 2);
    const nodes = SKILL_POINTS.map((point, index) => {
      const node = new THREE.Mesh(nodeGeometry, index === 2 || index === 4 ? accentMaterial : coreMaterial);
      node.position.set(...point);
      node.scale.setScalar(index === 2 ? 1.42 : index === 4 ? 1.18 : 1);
      pathway.add(node);
      return node;
    });

    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x8cb9d9,
      transparent: true,
      opacity: 0.42,
      blending: THREE.AdditiveBlending,
    });
    PATHS.forEach((path) => {
      const points = path.map((index) => new THREE.Vector3(...SKILL_POINTS[index]));
      pathway.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), lineMaterial));
    });

    const particleCount = mode === "ambient" ? 110 : 260;
    const particlePositions = new Float32Array(particleCount * 3);
    for (let index = 0; index < particleCount; index += 1) {
      const offset = index * 3;
      particlePositions[offset] = (Math.random() - 0.5) * 6.2;
      particlePositions[offset + 1] = (Math.random() - 0.5) * 4.1;
      particlePositions[offset + 2] = (Math.random() - 0.5) * 2.8 - 0.5;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
    const particles = new THREE.Points(
      particleGeometry,
      new THREE.PointsMaterial({ color: 0xe7dcc0, size: 0.018, transparent: true, opacity: 0.58, sizeAttenuation: true }),
    );
    scene.add(particles);

    const haloGeometry = new THREE.TorusGeometry(1.88, 0.006, 8, 180);
    const halo = new THREE.Mesh(
      haloGeometry,
      new THREE.MeshBasicMaterial({ color: 0xd7b671, transparent: true, opacity: 0.24 }),
    );
    halo.rotation.set(0.92, 0.18, -0.28);
    pathway.add(halo);

    scene.add(new THREE.AmbientLight(0xc2d5ff, 1.5));
    const keyLight = new THREE.PointLight(0x65bcff, 12, 12);
    keyLight.position.set(-2.5, 2.6, 3.8);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight(0xe3bd6e, 9, 10);
    rimLight.position.set(2.8, -1.8, 2.4);
    scene.add(rimLight);

    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const targetRotation = new THREE.Vector2(0, 0);
    const isAmbient = mode === "ambient";
    const isWindowPointer = isAmbient || mode === "journey";
    const onPointerMove = (event) => {
      if (motionPreference.matches || document.hidden) return;
      const bounds = host.getBoundingClientRect();
      const x = isAmbient ? event.clientX / Math.max(1, window.innerWidth) : (event.clientX - bounds.left) / bounds.width;
      const y = isAmbient ? event.clientY / Math.max(1, window.innerHeight) : (event.clientY - bounds.top) / bounds.height;
      targetRotation.set((y - 0.5) * 0.24, (x - 0.5) * 0.34);
    };
    const onPointerLeave = () => targetRotation.set(0, 0);
    const onJourneyScroll = () => {
      if (mode !== "journey" || motionPreference.matches) return;
      const bounds = host.getBoundingClientRect();
      const progress = THREE.MathUtils.clamp((window.innerHeight - bounds.top) / Math.max(1, window.innerHeight + bounds.height), 0, 1);
      targetRotation.x = (progress - 0.5) * 0.34;
      targetRotation.y = (progress - 0.5) * 0.52;
    };
    if (mode === "journey") window.addEventListener("scroll", onJourneyScroll, { passive: true });
    (isWindowPointer ? window : host).addEventListener("pointermove", onPointerMove, { passive: true });
    host.addEventListener("pointerleave", onPointerLeave);

    const resizeObserver = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.position.z = width < 600 ? 7.3 : 6.4;
      camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    });
    resizeObserver.observe(host);

    let frameId;
    let animationRunning = false;
    let inView = true;
    const startedAt = performance.now();
    const canAnimate = () => !motionPreference.matches && !document.hidden && inView;
    const stop = () => {
      if (frameId != null) window.cancelAnimationFrame(frameId);
      frameId = undefined;
      animationRunning = false;
    };
    const render = () => {
      animationRunning = true;
      const time = (performance.now() - startedAt) / 1000;
      if (canAnimate()) {
        pathway.rotation.y += (targetRotation.y - pathway.rotation.y) * 0.035;
        pathway.rotation.x += (targetRotation.x - pathway.rotation.x) * 0.035;
        pathway.rotation.z = Math.sin(time * 0.22) * 0.035;
        particles.rotation.y = time * 0.012;
        nodes.forEach((node, index) => {
          node.position.y = SKILL_POINTS[index][1] + Math.sin(time * 0.7 + index * 1.2) * 0.035;
        });
      }
      renderer.render(scene, camera);
      if (canAnimate()) frameId = window.requestAnimationFrame(render);
      else animationRunning = false;
    };

    const syncAnimation = () => {
      if (canAnimate() && !animationRunning) render();
      else if (!canAnimate()) {
        stop();
        if (motionPreference.matches) {
          pathway.rotation.set(0, 0, 0);
          particles.rotation.set(0, 0, 0);
          nodes.forEach((node, index) => { node.position.y = SKILL_POINTS[index][1]; });
        }
        renderer.render(scene, camera);
      }
    };
    const visibilityObserver = mode !== "full" ? new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      syncAnimation();
    }, { threshold: 0.01 }) : null;
    visibilityObserver?.observe(host);
    const onVisibilityChange = () => syncAnimation();
    document.addEventListener("visibilitychange", onVisibilityChange);
    const onMotionPreferenceChange = () => {
      syncAnimation();
    };
    motionPreference.addEventListener?.("change", onMotionPreferenceChange);
    render();

    return () => {
      stop();
      resizeObserver.disconnect();
      visibilityObserver?.disconnect();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (mode === "journey") window.removeEventListener("scroll", onJourneyScroll);
      motionPreference.removeEventListener?.("change", onMotionPreferenceChange);
      (isWindowPointer ? window : host).removeEventListener("pointermove", onPointerMove);
      host.removeEventListener("pointerleave", onPointerLeave);
      scene.traverse((object) => {
        if (object.geometry) object.geometry.dispose();
        if (object.material) {
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
      host.classList.remove("has-webgl");
    };
  }, []);

  return (
    <div ref={hostRef} className={`career-constellation ${className}`} aria-hidden={mode === "ambient" ? "true" : undefined} role={mode === "ambient" ? undefined : "img"} aria-label={mode === "ambient" ? undefined : "An animated constellation connecting learning, practice, proof, and opportunity"}>
      <div className="career-constellation-fallback" aria-hidden="true" />
    </div>
  );
}
