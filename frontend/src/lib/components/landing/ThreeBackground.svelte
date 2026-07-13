<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  let canvas: HTMLCanvasElement;
  let THREE: any;
  let scene: any, camera: any, renderer: any;
  let nodes: any[] = [];
  let edges: any[] = [];
  let packets: any[] = [];
  let nodePositions: Float32Array;
  let edgePairs: number[][] = [];
  let animationId: number;
  let mouseX = 0, mouseY = 0;
  let targetRotX = 0, targetRotY = 0;

  const NODE_COUNT = typeof window !== 'undefined' && window.innerWidth < 768 ? 40 : 80;
  const SPHERE_RADIUS = 14;
  const EDGE_DIST_THRESHOLD = 8;
  const PACKET_COUNT = 8;
  const ROTATION_SPEED = 0.003;
  const MOUSE_INFLUENCE = 0.05;

  const tempVec = { x: 0, y: 0, z: 0 };

  function hexToRgb(hex: string) {
    const r = parseInt(hex.slice(1, 3), 16),
          g = parseInt(hex.slice(3, 5), 16),
          b = parseInt(hex.slice(5, 7), 16);
    return { r: r / 255, g: g / 255, b: b / 255 };
  }

  function getBrandColor() {
    const html = document.documentElement;
    const brand = getComputedStyle(html).getPropertyValue('--brand').trim();
    if (brand.startsWith('#')) return hexToRgb(brand);
    return { r: 0.3, g: 0.62, b: 0.42 };
  }

  function buildScene() {
    if (canvas.clientWidth === 0 || canvas.clientHeight === 0) return;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(60, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
    camera.position.set(0, 2, 22);
    camera.lookAt(0, 0, 0);

    renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
    });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);

    const brand = getBrandColor();

    nodePositions = new Float32Array(NODE_COUNT * 3);
    for (let i = 0; i < NODE_COUNT; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = SPHERE_RADIUS * Math.cbrt(Math.random());
      nodePositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      nodePositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      nodePositions[i * 3 + 2] = r * Math.cos(phi);
    }

    const nodeGeo = new THREE.BufferGeometry();
    nodeGeo.setAttribute('position', new THREE.BufferAttribute(nodePositions, 3));
    const nodeMat = new THREE.PointsMaterial({
      color: new THREE.Color(brand.r, brand.g, brand.b),
      size: 0.25,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const nodeMesh = new THREE.Points(nodeGeo, nodeMat);
    scene.add(nodeMesh);
    nodes.push(nodeMesh);

    edgePairs = [];
    const edgePositions: number[] = [];
    for (let i = 0; i < NODE_COUNT; i++) {
      for (let j = i + 1; j < NODE_COUNT; j++) {
        const dx = nodePositions[i * 3] - nodePositions[j * 3];
        const dy = nodePositions[i * 3 + 1] - nodePositions[j * 3 + 1];
        const dz = nodePositions[i * 3 + 2] - nodePositions[j * 3 + 2];
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist < EDGE_DIST_THRESHOLD && Math.random() < 0.3) {
          edgePairs.push([i, j]);
          edgePositions.push(nodePositions[i * 3], nodePositions[i * 3 + 1], nodePositions[i * 3 + 2]);
          edgePositions.push(nodePositions[j * 3], nodePositions[j * 3 + 1], nodePositions[j * 3 + 2]);
        }
      }
    }
    if (edgePairs.length === 0) {
      edgePairs.push([0, 1]);
      edgePositions.push(nodePositions[0], nodePositions[1], nodePositions[2]);
      edgePositions.push(nodePositions[3], nodePositions[4], nodePositions[5]);
    }

    const edgeGeo = new THREE.BufferGeometry();
    edgeGeo.setAttribute('position', new THREE.Float32BufferAttribute(edgePositions, 3));
    const edgeMat = new THREE.LineBasicMaterial({
      color: new THREE.Color(brand.r, brand.g, brand.b),
      transparent: true,
      opacity: 0.12,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const edgeMesh = new THREE.LineSegments(edgeGeo, edgeMat);
    scene.add(edgeMesh);
    edges.push(edgeMesh);

    const packetGeo = new THREE.SphereGeometry(0.15, 8, 8);
    for (let i = 0; i < PACKET_COUNT; i++) {
      const mesh = new THREE.Mesh(packetGeo, new THREE.MeshBasicMaterial({
        color: new THREE.Color(brand.r, brand.g, brand.b),
        transparent: true,
        opacity: 0.9,
      }));
      const pairIdx = Math.floor(Math.random() * edgePairs.length);
      const pair = edgePairs[pairIdx] || [0, 1];
      const t = Math.random();
      mesh.position.set(
        nodePositions[pair[0] * 3] * (1 - t) + nodePositions[pair[1] * 3] * t,
        nodePositions[pair[0] * 3 + 1] * (1 - t) + nodePositions[pair[1] * 3 + 1] * t,
        nodePositions[pair[0] * 3 + 2] * (1 - t) + nodePositions[pair[1] * 3 + 2] * t,
      );
      scene.add(mesh);
      packets.push({
        mesh,
        pairIdx,
        t,
        speed: 0.002 + Math.random() * 0.004,
        glow: new THREE.Mesh(
          new THREE.SphereGeometry(0.3, 8, 8),
          new THREE.MeshBasicMaterial({
            color: new THREE.Color(brand.r, brand.g, brand.b),
            transparent: true,
            opacity: 0.2,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
          }),
        ),
      });
      scene.add(packets[i].glow);
    }

    scene.userData = { nodeMat, edgeMat, nodeMesh, edgeMesh };
  }

  function updateColors() {
    const brand = getBrandColor();
    if (scene?.userData?.nodeMat) {
      scene.userData.nodeMat.color.setRGB(brand.r, brand.g, brand.b);
    }
    if (scene?.userData?.edgeMat) {
      scene.userData.edgeMat.color.setRGB(brand.r, brand.g, brand.b);
    }
    for (const p of packets) {
      p.mesh.material.color.setRGB(brand.r, brand.g, brand.b);
      p.glow.material.color.setRGB(brand.r, brand.g, brand.b);
    }
  }

  function animate() {
    targetRotX += (mouseY * 0.2 - targetRotX) * MOUSE_INFLUENCE;
    targetRotY += (mouseX * 0.2 - targetRotY) * MOUSE_INFLUENCE;

    nodes[0].rotation.y += ROTATION_SPEED;
    nodes[0].rotation.x += targetRotX * 0.01;
    edges[0].rotation.copy(nodes[0].rotation);

    for (const p of packets) {
      const pair = edgePairs[p.pairIdx];
      if (!pair) continue;
      p.t += p.speed;
      if (p.t > 1) {
        p.t = 0;
        p.pairIdx = Math.floor(Math.random() * edgePairs.length);
      }
      const i1 = pair[0], i2 = pair[1];
      tempVec.x = nodePositions[i1 * 3] * (1 - p.t) + nodePositions[i2 * 3] * p.t;
      tempVec.y = nodePositions[i1 * 3 + 1] * (1 - p.t) + nodePositions[i2 * 3 + 1] * p.t;
      tempVec.z = nodePositions[i1 * 3 + 2] * (1 - p.t) + nodePositions[i2 * 3 + 2] * p.t;
      p.mesh.position.copy(nodes[0].position).add(tempVec);
      p.glow.position.copy(p.mesh.position);
      const pulse = 0.5 + 0.5 * Math.sin(Date.now() * 0.002 + p.pairIdx);
      p.mesh.material.opacity = 0.5 + 0.5 * pulse;
      p.glow.material.opacity = 0.05 + 0.15 * pulse;
      const scale = 1 + 0.5 * pulse;
      p.glow.scale.set(scale, scale, scale);
    }

    renderer.render(scene, camera);
    animationId = requestAnimationFrame(animate);
  }

  function onMouseMove(e: MouseEvent) {
    mouseX = (e.clientX / window.innerWidth) * 2 - 1;
    mouseY = (e.clientY / window.innerHeight) * 2 - 1;
  }

  function onResize() {
    if (!camera || !renderer) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }

  let observer: MutationObserver;

  onMount(async () => {
    THREE = await import('three');
    buildScene();

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('resize', onResize);
    animate();

    observer = new MutationObserver(() => updateColors());
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  });

  onDestroy(() => {
    cancelAnimationFrame(animationId);
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('resize', onResize);
    observer?.disconnect();
    if (renderer) {
      renderer.dispose();
    }
  });
</script>

<canvas
  bind:this={canvas}
  class="three-bg"
  style="position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0"
></canvas>
