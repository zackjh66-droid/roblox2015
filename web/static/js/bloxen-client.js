/* BLOXEN client runtime — renders a preserved 2015 Roblox place file.
 *
 * What is real here:
 *   - geometry, sizes, positions, rotation matrices, colours (BrickColor palette),
 *     transparency, reflectance, material names, surface types, spawn points and
 *     Lighting values all come from the preserved place file via
 *     /api/place/<id>/geometry (see server/bloxen/placeview/geometry.py)
 *   - the R6 character is built from the genuine 2015 part dimensions and the
 *     2015 default physics constants (WalkSpeed 16, JumpPower 50, Gravity 196.2)
 *   - the stud / inlet surface pattern follows the surface types stored per face
 *
 * What is a reconstruction (and labelled as such in the menu panel):
 *   - HUD chrome (the original 2015 UI bitmaps ship inside the client package)
 *   - stud/inlet surface *textures* are generated here, not the client's bitmaps
 *   - walk/jump animation is procedural (the default R6 animation asset is not
 *     recovered; the motion matches the classic swing cycle)
 *   - CSG unions, meshes, terrain voxels are NOT drawn at all (no substitutes)
 */
import * as THREE from '/static/js/three.module.js';

const RUNTIME = document.getElementById('blx-runtime');
const GAME_ID = Number(RUNTIME.dataset.gameId);
const USERNAME = RUNTIME.dataset.user || 'Guest';

const PHYS = {
  gravity: 196.2,          // studs/s^2  (2015 default)
  walkSpeed: 16,           // studs/s     (2015 default)
  runSpeed: 16,
  jumpPower: 50,           // studs/s     (2015 default -> ~6.4 stud jump)
  stepHeight: 2.0,         // R6 stair climb
  characterHeight: 5.0,    // legs 2 + torso 2 + head 1
  characterRadius: 1.0,    // 2x2 torso
  cameraDistance: 11.5,    // classic camera default
  zoomMin: 6,
  zoomMax: 128,
};

const state = {
  geometry: null,
  position: new THREE.Vector3(0, 10, 0),
  velocity: new THREE.Vector3(),
  onGround: false,
  yaw: 0,
  camYaw: 0,
  camPitch: -0.32,
  camDist: PHYS.cameraDistance,
  freeCam: false,
  overview: false,
  overviewY: 120,
  freeCamPos: null,
  collisionIndex: null,
  spawnIndex: -1,
  studs: true,
  flipWedge: false,
  showStored: true,
  quality: 'medium',
  keys: new Set(),
  walkPhase: 0,
  jumping: false,
  fps: 0,
};

// ------------------------------------------------------------------ helpers
const el = (id) => document.getElementById(id);
const status = (t) => { const s = el('blx-load-status'); if (s) s.textContent = t; };
const progress = (p) => { const b = el('blx-bar-fill'); if (b) b.style.width = `${p}%`; };

function toast(msg, ms = 2600) {
  let t = document.querySelector('.blx-toast');
  if (!t) { t = document.createElement('div'); t.className = 'blx-toast'; RUNTIME.appendChild(t); }
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove('show'), ms);
}

function srgbToLinear(c) { return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }

// ------------------------------------------------- 2015 client surface textures
// The surface patterns are the *client's own* bitmaps, converted verbatim out of the
// verified 2015 WindowsPlayer package (0.205.0.61876) by tools/import_client_assets.py:
//
//   textures/client/studs.png   128x2048 atlas, 16 cells of 128x128 stacked vertically
//                               (cells 0-11 stud patterns, 12-15 square/inlet patterns)
//   textures/client/*.png       one diffuse per material (brick, wood, slate, ...)
//
// Nothing here is redrawn. The only judgement is WHICH atlas cell to show and at what
// scale; see CLIENT-ASSET-SCALE below — it is an open item, not a verified mapping.
const CLIENT_ATLAS_CELLS = 16;
// MEASURED from the atlas itself (tools/import_client_assets.py):
// each 128x128 cell contains a 2x2 arrangement of studs, so one cell spans 2 studs.
// The runtime's UVs are in studs (1 UV unit = 1 stud), so the texture must repeat
// 1/2 per stud horizontally, and 1/2 cell vertically within the 16-cell column.
const CELL_STUDS = 2;
const CLIENT_ASSET_SCALE = {
  studsCell: 0,          // cells 0-3: four "R" studs
  inletsCell: 8,         // cells 8-11: four recessed square inlets
  note: "Cell choice measured by inspection of the atlas (2x2 per cell); cells 4-7 and "
      + "12-15 are mixed R-stud/plain variants and are not used. Material bitmaps "
      + "(brick, wood, ...) tile once per stud: the 2015 engine's material feet-per-tile "
      + "could not be measured from the package alone, so this remains a BLOXEN choice.",
  repeat: [1 / CELL_STUDS, 1 / (CELL_STUDS * 16)],
};
let CLIENT_TEXTURES = null;          // filled in from /static/data/client-textures.json

async function loadClientTextures() {
  if (CLIENT_TEXTURES) return CLIENT_TEXTURES;
  const loader = new THREE.TextureLoader();
  let manifest = null;
  try {
    const res = await fetch('/static/data/client-textures.json');
    if (res.ok) manifest = await res.json();
  } catch (e) { manifest = null; }
  const tex = { materials: {}, atlas: null, sky: null, manifest };
  const load = (url) => new Promise((resolve) => {
    loader.load(url, (t) => {
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = 4;
      resolve(t);
    }, undefined, () => resolve(null));
  });
  if (manifest && manifest.materials) {
    // the full studs/inlet atlas is one file: 16 stacked cells
    const atlas = manifest.materials.studs;
    if (atlas) tex.atlas = await load('/static/' + atlas.file);
    for (const [name, info] of Object.entries(manifest.materials)) {
      if (name === 'studs') continue;
      const t = await load('/static/' + info.file);
      if (t) tex.materials[name] = t;
    }
  }
  // the client's own default skybox (six faces), used verbatim
  if (manifest && manifest.sky && manifest.sky.lf) {
    const face = (f) => manifest.sky[f] ? '/static/' + manifest.sky[f].file : null;
    const urls = ['rt', 'lf', 'up', 'dn', 'ft', 'bk'].map(face);
    if (urls.every(Boolean)) {
      tex.sky = await new Promise((resolve) => {
        new THREE.CubeTextureLoader().load(urls, (t) => {
          t.colorSpace = THREE.SRGBColorSpace;
          resolve(t);
        }, undefined, () => resolve(null));
      });
    }
  }
  CLIENT_TEXTURES = tex;
  window.__blxTextures = tex;
  return tex;
}

/** A surface texture for the given kind, or null when the client has no such bitmap. */
function surfaceTexture(kind) {
  const tex = CLIENT_TEXTURES;
  if (!tex) return null;
  const atlasCell = (cell) => {
    const t = tex.atlas.clone();
    t.needsUpdate = true;
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    const [rx, ry] = CLIENT_ASSET_SCALE.repeat;
    t.repeat.set(rx, ry);
    t.offset.set(0, cell / CLIENT_ATLAS_CELLS);
    return t;
  };
  if (kind === 'studs' && tex.atlas) return atlasCell(CLIENT_ASSET_SCALE.studsCell);
  if (kind === 'inlets' && tex.atlas) return atlasCell(CLIENT_ASSET_SCALE.inletsCell);
  if (kind === 'universal') return tex.materials.plastic || null;
  return null;
}

/** The client's real material bitmap for a part material, when one exists. */
function materialTexture(matName) {
  const tex = CLIENT_TEXTURES;
  if (!tex) return null;
  return tex.materials[String(matName).toLowerCase()] || null;
}

// ------------------------------------------------------------ base geometry
function uvAxesFor(nx, ny, nz) {
  const ax = Math.abs(nx), ay = Math.abs(ny), az = Math.abs(nz);
  if (ay >= ax && ay >= az) return [0, 2];        // top/bottom -> X,Z
  if (ax >= az) return [2, 1];                    // x faces    -> Z,Y
  return [0, 1];                                  // z faces    -> X,Y
}

/** Base geometries in a unit box (-0.5..0.5), three.js right-handed Y-up. */
function baseGeometries(flipWedge = false) {
  const box = new THREE.BoxGeometry(1, 1, 1);
  const sphere = new THREE.SphereGeometry(0.5, 16, 10);
  const cyl = new THREE.CylinderGeometry(0.5, 0.5, 1, 18, 1, false);  // along Y
  cyl.rotateZ(Math.PI / 2);                                            // Roblox: axis = X

  // Wedge: vertical face on +Z, slope descending to the bottom edge on -Z.
  // Orientation determined empirically from the preserved corpus (see
  // docs/CLIENT.md "Wedge orientation"); the menu exposes a flip toggle.
  const wedge = wedgeGeometry(flipWedge);
  const corner = cornerWedgeGeometry();
  const truss = trussGeometry();
  return { Block: box, Ball: sphere, Cylinder: cyl, Wedge: wedge,
           CornerWedge: corner, Truss: truss };
}

function faceQuad(a, b, c, d) { return [a, b, c, a, c, d]; }

function wedgeGeometry(flipped) {
  const s = flipped ? -1 : 1;
  const v = [
    [-0.5, -0.5, -0.5 * s], [0.5, -0.5, -0.5 * s], [-0.5, -0.5, 0.5 * s], [0.5, -0.5, 0.5 * s],
    [-0.5, 0.5, 0.5 * s], [0.5, 0.5, 0.5 * s],
  ];
  const quads = [
    [4, 5, 3, 2],        // +Z vertical face
    [4, 5, 1, 0],        // slope (up and toward -Z)
    [0, 1, 3, 2],        // bottom
    [0, 2, 4],           // -X triangle
    [1, 5, 3],           // +X triangle
  ];
  return geometryFromFaces(v, quads);
}

function cornerWedgeGeometry() {
  // Corner wedge: bottom quad with the apex at the top-back-left corner.
  const v = [[-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [-0.5, -0.5, 0.5],
             [-0.5, 0.5, 0.5]];
  const faces = [[1, 2, 3, 0], [4, 3, 0], [4, 1, 0], [4, 2, 1], [2, 4, 3]];
  return geometryFromFaces(v, faces);
}

function trussGeometry() {
  // 4 corner posts + braced diagonals, 2x2 cross-section, unit length on Y is
  // scaled by the part size. Classic Roblox truss look.
  const geos = [];
  const post = new THREE.BoxGeometry(0.22, 1, 0.22);
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    const g = post.clone();
    g.translate(x * 0.39, 0, z * 0.39);
    geos.push(g);
  }
  const brace = new THREE.BoxGeometry(0.14, 0.98, 0.14);
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    for (const dir of [1, -1]) {
      const g = brace.clone();
      g.rotateZ(dir * Math.PI / 4);
      g.translate(x * 0.39, 0, z * 0.39);
      geos.push(g);
    }
  }
  return mergeGeometries(geos);
}

function geometryFromFaces(verts, faces) {
  const pos = [], idx = [];
  for (const f of faces) {
    if (f.length === 3) { pos.push(...verts[f[0]], ...verts[f[1]], ...verts[f[2]]); }
    else { for (const p of faceQuad(verts[f[0]], verts[f[1]], verts[f[2]], verts[f[3]])) pos.push(...p); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  return g;
}

function mergeGeometries(geos) {
  const out = new THREE.BufferGeometry();
  const pos = [], nor = [], idx = [];
  let off = 0;
  for (const g of geos) {
    const gn = g.index ? g.toNonIndexed() : g;
    const p = gn.getAttribute('position');
    let n = gn.getAttribute('normal');
    if (!n) { gn.computeVertexNormals(); n = gn.getAttribute('normal'); }
    for (let i = 0; i < p.count; i++) {
      pos.push(p.getX(i), p.getY(i), p.getZ(i));
      nor.push(n.getX(i), n.getY(i), n.getZ(i));
    }
    off += p.count;
  }
  for (let i = 0; i < off; i++) idx.push(i);
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  out.setIndex(idx);
  return out;
}

// --------------------------------------------------------------- mesh build
const SURFACE_KIND = { 3: 'studs', 5: 'universal', 4: 'inlets' };

function buildWorld(geo, opts = {}) {
  const P = geo.parts, n = P.pos.length / 3;
  const rots = geo.rots, colors = geo.colors, shapes = geo.shapes, mats = geo.materials;
  const classNames = geo.classes;
  const colorLinear = colors.map((c) => new THREE.Color().setRGB(c[0] / 255, c[1] / 255, c[2] / 255, THREE.SRGBColorSpace));
  const base = baseGeometries(opts.flipWedge === true);
  // face order in three's BoxGeometry: +X, -X, +Y, -Y, +Z, -Z
  const BOX_FACE_KEYS = [12, 8, 0, 4, 16, 20];
  const buckets = new Map();
  const storedMeshes = [];
  const collision = [];               // {min:[x,y,z], max:[x,y,z]}
  let rendered = 0;

  const bucketFor = (key) => {
    let b = buckets.get(key);
    if (!b) {
      b = { pos: [], nor: [], uv: [], col: [], idx: [], count: 0, key };
      buckets.set(key, b);
    }
    return b;
  };

  for (let i = 0; i < n; i++) {
    const flags = P.flags[i];
    const invisible = (flags & 4) !== 0;
    const collide = (flags & 1) !== 0;
    const px = P.pos[3 * i], py = P.pos[3 * i + 1], pz = P.pos[3 * i + 2];
    const sx = P.size[3 * i], sy = P.size[3 * i + 1], sz = P.size[3 * i + 2];
    if (collide) {
      collision.push({ i, c: [px, py, pz], h: [Math.abs(sx) / 2, Math.abs(sy) / 2, Math.abs(sz) / 2] });
    }
    if (invisible) continue;
    const shapeName = shapes[P.shape[i]] || 'Block';
    const shape = base[P.shape[i] === 3 ? 'Wedge' : P.shape[i] === 4 ? 'CornerWedge'
      : P.shape[i] === 5 ? 'Truss' : shapeName] || base.Block;
    const rot = rots[P.rot[i]];
    const mat = mats[P.mat[i]] || 'Plastic';
    const alpha = P.alpha[i] / 255;
    const refl = P.refl[i] / 255;
    const colIndex = P.col[i];
    const col = colorLinear[colIndex];
    const surf = P.surf ? P.surf[i] : 0;
    const containerName = geo.containers && P.container ? geo.containers[P.container[i]] : 'Workspace';
    const containerGroup = containerName === 'Workspace' ? 'ws' : 'stored';

    const normalMatrix = [
      [rot[0], rot[1], rot[2]],
      [rot[3], rot[4], rot[5]],
      [rot[6], rot[7], rot[8]],
    ];
    const posAttr = shape.getAttribute('position');
    const norAttr = shape.getAttribute('normal');
    const groups = shape.groups && shape.groups.length ? shape.groups : [{ start: 0, count: (shape.index ? shape.index.count : posAttr.count), materialIndex: -1 }];
    const indexArr = shape.index ? shape.index.array : null;

    for (let g = 0; g < groups.length; g++) {
      const grp = groups[g];
      let surfaceKey = 0;
      if (shapeName === 'Block' || shapeName === 'Wedge') {
        const faceIdx = groups.length === 6 ? g : 0;
        surfaceKey = (surf >> (BOX_FACE_KEYS[Math.min(faceIdx, 5)] || 0)) & 0xF;
      }
      const kind = STATE_STUDS() ? (SURFACE_KIND[surfaceKey] || 'none') : 'none';
      const alphaBucket = alpha >= 0.999 ? 3 : alpha >= 0.6 ? 2 : alpha >= 0.25 ? 1 : 0;
      const b = bucketFor(`${mat}|${alphaBucket}|${kind}|${containerGroup}`);
      const startCount = b.count;

      const emitVertex = (vi) => {
        const lx = posAttr.getX(vi), ly = posAttr.getY(vi), lz = posAttr.getZ(vi);
        const wx = lx * sx, wy = ly * sy, wz = lz * sz;
        // rotate then translate (Roblox CFrame basis maps 1:1 to three axes)
        const rx = normalMatrix[0][0] * wx + normalMatrix[0][1] * wy + normalMatrix[0][2] * wz;
        const ry = normalMatrix[1][0] * wx + normalMatrix[1][1] * wy + normalMatrix[1][2] * wz;
        const rz = normalMatrix[2][0] * wx + normalMatrix[2][1] * wy + normalMatrix[2][2] * wz;
        b.pos.push(px + rx, py + ry, pz + rz);
        const nx = norAttr.getX(vi), ny = norAttr.getY(vi), nz = norAttr.getZ(vi);
        b.nor.push(
          normalMatrix[0][0] * nx + normalMatrix[0][1] * ny + normalMatrix[0][2] * nz,
          normalMatrix[1][0] * nx + normalMatrix[1][1] * ny + normalMatrix[1][2] * nz,
          normalMatrix[2][0] * nx + normalMatrix[2][1] * ny + normalMatrix[2][2] * nz);
        const [ua, va] = uvAxesFor(nx, ny, nz);
        const w = [lx * sx, ly * sy, lz * sz];
        b.uv.push(w[ua], w[va]);
        b.col.push(col.r, col.g, col.b);
      };

      const vertsInGroup = [];
      if (indexArr) {
        for (let k = grp.start; k < grp.start + grp.count; k++) vertsInGroup.push(indexArr[k]);
      } else {
        for (let k = grp.start; k < grp.start + grp.count; k++) vertsInGroup.push(k);
      }
      // weld duplicate vertices inside the group so indices stay small
      const remap = new Map();
      for (const vi of vertsInGroup) {
        let local = remap.get(vi);
        if (local === undefined) { local = b.count - startCount; remap.set(vi, local); emitVertex(vi); b.count++; }
        b.idx.push(startCount + local);
      }
      rendered++;
    }
  }

  const world = new THREE.Group();
  let drawCalls = 0;
  for (const b of buckets.values()) {
    const [matName, alphaBucket, kind, containerGroup] = b.key.split('|');
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(b.pos, 3));
    geom.setAttribute('normal', new THREE.Float32BufferAttribute(b.nor, 3));
    geom.setAttribute('uv', new THREE.Float32BufferAttribute(b.uv, 2));
    geom.setAttribute('color', new THREE.Float32BufferAttribute(b.col, 3));
    geom.setIndex(b.idx);
    const alpha = [0.35, 0.7, 0.9, 1.0][Number(alphaBucket)];
    const matOpts = {
      vertexColors: true,
      transparent: alpha < 1,
      opacity: alpha,
      side: THREE.FrontSide,
      flatShading: false,
    };
    // surface pattern (studs/inlet) wins; otherwise the material's own 2015 bitmap
    const surfTex = kind !== 'none' ? surfaceTexture(kind) : null;
    const matTex = surfTex || materialTexture(matName);
    if (matTex) matOpts.map = matTex;
    if (matName === 'Neon') { matOpts.emissive = new THREE.Color(0xffffff); matOpts.emissiveIntensity = 0.35; }
    if (matName === 'Glass' || matName === 'ForceField') { matOpts.transparent = true; matOpts.opacity = 0.4; }
    const material = new THREE.MeshLambertMaterial(matOpts);
    const mesh = new THREE.Mesh(geom, material);
    mesh.name = `blx-bucket-${b.key}`;
    mesh.matrixAutoUpdate = false;
    mesh.userData.containerGroup = containerGroup;
    if (containerGroup === 'stored') storedMeshes.push(mesh);
    world.add(mesh);
    drawCalls++;
  }
  return { world, collision, rendered, drawCalls, bucketCount: buckets.size, storedMeshes };
}

function STATE_STUDS() { return state.studs; }

function disposeWorld(world) {
  world.traverse((o) => {
    if (o.isMesh) {
      o.geometry.dispose();
      if (o.material && o.material.map) o.material.map.dispose();
      if (o.material) o.material.dispose();
    }
  });
}

// ------------------------------------------------------------------- sky
function buildSky(geo, scene) {
  const L = geo.lighting || {};
  const clock = L.time_of_day ? Number(String(L.time_of_day).split(':')[0]) : (L.clock_time || 14);
  const t = Math.min(1, Math.max(0, (clock - 6) / 12));       // 6h..18h daylight
  const top = new THREE.Color().setRGB(...[0.05 + 0.24 * t, 0.15 + 0.42 * t, 0.32 + 0.55 * t], THREE.SRGBColorSpace);
  const bottom = new THREE.Color().setRGB(...[0.45 + 0.35 * t, 0.6 + 0.3 * t, 0.72 + 0.25 * t], THREE.SRGBColorSpace);
  // the client's own default skybox (content/sky/null_plainsky512_*.jpg in the 2015
  // package). Only if that conversion is present; otherwise the gradient below stands in
  // and the panel says so.
  if (CLIENT_TEXTURES && CLIENT_TEXTURES.sky) {
    const skyBox = new THREE.Mesh(
      new THREE.SphereGeometry(4000, 32, 16),
      new THREE.MeshBasicMaterial({ map: CLIENT_TEXTURES.sky, side: THREE.BackSide,
                                    depthWrite: false }));
    skyBox.frustumCulled = false;
    scene.add(skyBox);
  } else {
  const skyGeo = new THREE.SphereGeometry(4000, 24, 16);
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    uniforms: { topColor: { value: top }, bottomColor: { value: bottom } },
    vertexShader: `varying float vH; void main(){ vH = normalize(position).y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: `uniform vec3 topColor; uniform vec3 bottomColor; varying float vH;
      void main(){ float h = clamp(vH*0.5+0.5, 0.0, 1.0); gl_FragColor = vec4(mix(bottomColor, topColor, h), 1.0); }`,
  });
  const sky = new THREE.Mesh(skyGeo, skyMat);
  sky.frustumCulled = false;
  scene.add(sky);
  }
  // ambient wrap so the classic flat-lit look is not crushed by linear workflow
  scene.add(new THREE.AmbientLight(0xffffff, 0.42));

  // Lighting: ambient from the place file, one sun for the 2015 flat-lighting look
  const amb = L.ambient || [0, 0, 0];
  const outAmb = L.outdoor_ambient || [128, 128, 128];
  const ambColor = new THREE.Color().setRGB(
    (amb[0] / 255) * 0.5 + (outAmb[0] / 255) * 0.5,
    (amb[1] / 255) * 0.5 + (outAmb[1] / 255) * 0.5,
    (amb[2] / 255) * 0.5 + (outAmb[2] / 255) * 0.5, THREE.SRGBColorSpace);
  const hemisphere = new THREE.HemisphereLight(0xffffff, 0x8899aa, 2.45);
  hemisphere.color.copy(ambColor).lerp(new THREE.Color(0xffffff), 0.55);
  scene.add(hemisphere);
  const sun = new THREE.DirectionalLight(0xfff4e0, 2.55 * (0.35 + 0.65 * t));
  const ang = Math.PI * (clock / 24);
  const sunOffset = new THREE.Vector3(Math.cos(ang) * 500, Math.sin(Math.PI - ang) * 500 + 60, 200);
  sun.position.copy(sunOffset);
  scene.add(sun);
  scene.add(sun.target);

  const fogCol = L.fog_color || [192, 192, 192];
  if (L.fog_end && L.fog_end < 100000) {
    scene.fog = new THREE.Fog(new THREE.Color().setRGB(fogCol[0] / 255, fogCol[1] / 255, fogCol[2] / 255, THREE.SRGBColorSpace),
      Math.max(0, L.fog_start || 0), L.fog_end);
  }
  return { sun, sunOffset, hemisphere, clock, daylight: t };
}

// --------------------------------------------------------------- character
// R6 rig: genuine 2015 part dimensions (studs) and default colours.
const R6 = {
  Torso: { size: [2, 2, 1], offset: [0, 3, 0], color: 'Bright blue' },
  Head: { size: [2, 1, 1], offset: [0, 4.5, 0], color: 'Bright yellow' },
  'Left Arm': { size: [1, 2, 1], offset: [-1.5, 3, 0], color: 'Bright yellow' },
  'Right Arm': { size: [1, 2, 1], offset: [1.5, 3, 0], color: 'Bright yellow' },
  'Left Leg': { size: [1, 2, 1], offset: [-0.5, 1, 0], color: 'Bright green' },
  'Right Leg': { size: [1, 2, 1], offset: [0.5, 1, 0], color: 'Bright green' },
};

function buildCharacter(palette) {
  const group = new THREE.Group();
  const parts = {};
  for (const [name, def] of Object.entries(R6)) {
    const col = palette[def.color] || [163, 162, 165];
    const color = new THREE.Color().setRGB(col[0] / 255, col[1] / 255, col[2] / 255, THREE.SRGBColorSpace);
    const geo = new THREE.BoxGeometry(def.size[0], def.size[1], def.size[2]);
    const mat = new THREE.MeshLambertMaterial({ color, vertexColors: false });
    const mesh = new THREE.Mesh(geo, mat);
    const pivot = new THREE.Group();                 // joint pivot for animation
    pivot.position.set(...def.offset);
    mesh.position.set(0, 0, 0);
    pivot.add(mesh);
    group.add(pivot);
    parts[name] = { pivot, mesh, def };
  }
  // R6 face: the classic face decal asset is not recovered -> nothing is drawn.
  return { group, parts };
}

function animateCharacter(parts, speed, dt, airborne) {
  const walking = speed > 0.4 && !airborne;
  if (airborne) {
    for (const [name, p] of Object.entries(parts)) {
      const target = name.includes('Arm') ? (name.includes('Left') ? -2.5 : -2.5) : 0;
      p.pivot.rotation.z += ((name.includes('Arm') ? (name.includes('Left') ? 0.35 : -0.35) : 0) - p.pivot.rotation.z) * Math.min(1, dt * 8);
      p.pivot.rotation.x += ((name.includes('Arm') ? -2.2 : 0.25) - p.pivot.rotation.x) * Math.min(1, dt * 8);
    }
    return;
  }
  if (walking) {
    state.walkPhase += dt * (speed / 3.4);
  } else {
    state.walkPhase += dt * 0.6;                    // gentle idle sway (reconstruction)
  }
  const amp = walking ? 0.62 : 0.03;
  const s = Math.sin(state.walkPhase * 2);
  parts['Left Leg'].pivot.rotation.x = s * amp;
  parts['Right Leg'].pivot.rotation.x = -s * amp;
  parts['Left Arm'].pivot.rotation.x = -s * amp;
  parts['Right Arm'].pivot.rotation.x = s * amp;
  for (const n of ['Head']) parts[n].pivot.rotation.x = walking ? 0.06 : Math.sin(state.walkPhase) * 0.02;
  parts.Torso.pivot.rotation.x = walking ? 0.08 : 0;
}

// ---------------------------------------------------------------- physics
function makeCollisionIndex(collision, cell = 8) {
  const grid = new Map();
  const key = (x, y, z) => `${x},${y},${z}`;
  for (const c of collision) {
    const x0 = Math.floor((c.c[0] - c.h[0]) / cell), x1 = Math.floor((c.c[0] + c.h[0]) / cell);
    const y0 = Math.floor((c.c[1] - c.h[1]) / cell), y1 = Math.floor((c.c[1] + c.h[1]) / cell);
    const z0 = Math.floor((c.c[2] - c.h[2]) / cell), z1 = Math.floor((c.c[2] + c.h[2]) / cell);
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) for (let z = z0; z <= z1; z++) {
      const k = key(x, y, z);
      let arr = grid.get(k);
      if (!arr) { arr = []; grid.set(k, arr); }
      arr.push(c);
    }
  }
  return { grid, cell, key };
}

function collides(index, pos, radius, height) {
  const { grid, cell, key } = index;
  const minY = pos.y, maxY = pos.y + height;
  const x0 = Math.floor((pos.x - radius) / cell), x1 = Math.floor((pos.x + radius) / cell);
  const y0 = Math.floor(minY / cell), y1 = Math.floor(maxY / cell);
  const z0 = Math.floor((pos.z - radius) / cell), z1 = Math.floor((pos.z + radius) / cell);
  const seen = new Set();
  for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) for (let z = z0; z <= z1; z++) {
    const arr = grid.get(key(x, y, z));
    if (!arr) continue;
    for (const c of arr) {
      if (seen.has(c.i)) continue;
      seen.add(c.i);
      const [cx, cy, cz] = c.c, [hx, hy, hz] = c.h;
      if (Math.abs(pos.x - cx) < hx + radius &&
          Math.abs(pos.z - cz) < hz + radius &&
          minY < cy + hy && maxY > cy - hy) return c;
    }
  }
  return null;
}

/** Highest collider top surface under the character within [lowY, highY].
 *  Sweeping a range (instead of probing one point) prevents falling through
 *  floors at high vertical speed. Returns -Infinity when nothing is in range. */
function groundTopInRange(index, pos, radius, lowY, highY) {
  let best = -Infinity;
  const { grid, cell, key } = index;
  const x0 = Math.floor((pos.x - radius) / cell), x1 = Math.floor((pos.x + radius) / cell);
  const z0 = Math.floor((pos.z - radius) / cell), z1 = Math.floor((pos.z + radius) / cell);
  const y0 = Math.floor((lowY - cell) / cell), y1 = Math.floor((highY + cell) / cell);
  const seen = new Set();
  for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) for (let z = z0; z <= z1; z++) {
    const arr = grid.get(key(x, y, z));
    if (!arr) continue;
    for (const c of arr) {
      if (seen.has(c.i)) continue;
      seen.add(c.i);
      const [cx, cy, cz] = c.c, [hx, hy, hz] = c.h;
      if (Math.abs(pos.x - cx) < hx + radius && Math.abs(pos.z - cz) < hz + radius) {
        const top = cy + hy;
        if (top <= highY && top >= lowY && top > best) best = top;
      }
    }
  }
  return best;
}

/** March a ray through the collider grid, returning the distance to the first hit
 *  (camera occlusion, like the classic client pulling the camera in). */
function rayHitDistance(index, origin, dir, maxDist, inflate = 0.35) {
  const { grid, cell, key } = index;
  const step = 0.4;
  const steps = Math.min(200, Math.ceil(maxDist / step));
  for (let s = 1; s <= steps; s++) {
    const t = s * step;
    const x = origin.x + dir.x * t, y = origin.y + dir.y * t, z = origin.z + dir.z * t;
    const gx = Math.floor(x / cell), gy = Math.floor(y / cell), gz = Math.floor(z / cell);
    for (let ax = gx - 1; ax <= gx + 1; ax++) for (let ay = gy - 1; ay <= gy + 1; ay++) {
      for (let az = gz - 1; az <= gz + 1; az++) {
        const arr = grid.get(key(ax, ay, az));
        if (!arr) continue;
        for (let n = 0; n < arr.length; n++) {
          const c = arr[n];
          const [cx, cy, cz] = c.c, [hx, hy, hz] = c.h;
          if (Math.abs(x - cx) < hx + inflate && Math.abs(y - cy) < hy + inflate
              && Math.abs(z - cz) < hz + inflate) return t;
        }
      }
    }
  }
  return maxDist;
}

/** How much of the view is blocked by geometry right in front of the camera. */
function viewBlockedRatio(index, camera, forward) {
  const probes = [
    forward,
    forward.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.32),
    forward.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), -0.32),
    forward.clone().applyAxisAngle(new THREE.Vector3(1, 0, 0), 0.22),
    forward.clone().applyAxisAngle(new THREE.Vector3(1, 0, 0), -0.22),
  ];
  let blocked = 0;
  for (const p of probes) {
    if (rayHitDistance(index, camera, p.normalize(), 3.0, 0.1) < 3.0) blocked++;
  }
  return blocked / probes.length;
}

/** At a spawn, choose the yaw whose view is most open. The SpawnLocation's own
 *  facing is kept whenever it already looks into open space; this only rescues
 *  spawns authored facing a wall or in a corner. */
function bestSpawnYaw(index, pos, authoredYaw) {
  const eye = new THREE.Vector3(pos.x, pos.y + 3.0, pos.z);
  const probeYaw = (yaw) => {
    const forward = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
    // required clearing distance: 3 studs (the same threshold the blocked-view
    // metric uses), so the choice matches what the player actually sees
    return rayHitDistance(index, eye, forward, 60, 1.0);
  };
  const authored = probeYaw(authoredYaw);
  if (authored > 8) return authoredYaw;
  let bestYaw = authoredYaw, bestDist = authored;
  for (let a = 0; a < 16; a++) {
    const yaw = (a / 16) * Math.PI * 2;
    const d = probeYaw(yaw);
    if (d > bestDist + 2) { bestDist = d; bestYaw = yaw; }
  }
  return bestYaw;
}

/** Find a standable spot near `p`: closest ground surface with clear space above.
 *  Used when a place's SpawnLocations float above the void (the map's real
 *  geometry is then used as the standing surface). */
function nearestStandable(index, p, radius, height, maxRange = 24) {
  let bestPos = null, bestDrop = Infinity;
  const offsets = [[0, 0]];
  for (let r = 4; r <= maxRange; r += 4) {
    for (let a = 0; a < 12; a++) {
      const ang = (a / 12) * Math.PI * 2;
      offsets.push([Math.cos(ang) * r, Math.sin(ang) * r]);
    }
  }
  for (const [dx, dz] of offsets) {
    const candidate = new THREE.Vector3(p.x + dx, p.y, p.z + dz);
    // prefer a surface just below the spawn, then fall back to a large range
    for (const range of [60, 400, 2000]) {
      const ground = groundTopInRange(index, candidate, radius * 0.85, p.y - range, p.y + 0.05);
      if (ground === -Infinity) continue;
      candidate.y = ground + 0.1;
      if (!collides(index, candidate, radius, height)) {
        const drop = Math.abs(ground - p.y);
        if (drop < bestDrop) { bestDrop = drop; bestPos = candidate.clone(); }
      }
      break;
    }
  }
  return bestPos;
}

/** Pick the SpawnLocation with the most open space around it. */
function bestSpawnIndex(g, index) {
  const spawns = g.spawns && g.spawns.pos ? g.spawns.pos : [];
  if (!spawns.length) return -1;
  let best = 0, bestClear = -1;
  for (let i = 0; i < spawns.length; i++) {
    const [x, y, z] = spawns[i];
    let blocked = 0;
    const { grid, cell, key } = index;
    for (let ax = -2; ax <= 2; ax++) for (let ay = -2; ay <= 2; ay++) for (let az = -2; az <= 2; az++) {
      const arr = grid.get(key(Math.floor(x / cell) + ax, Math.floor(y / cell) + ay,
                               Math.floor(z / cell) + az));
      if (!arr) continue;
      for (const c of arr) {
        if (Math.abs(c.c[0] - x) < c.h[0] + 3 && Math.abs(c.c[1] - y) < c.h[1] + 3.5
            && Math.abs(c.c[2] - z) < c.h[2] + 3) blocked++;
      }
    }
    // a spawn with ground beneath it beats one floating over the void
    const ground = groundTopInRange(index, new THREE.Vector3(x, y, z), 1.0, y - 2000, y + 0.05);
    const score = blocked + (ground === -Infinity ? 1000 : 0);
    const bestGround = best < 0 ? -Infinity
      : groundTopInRange(index, new THREE.Vector3(spawns[best][0], spawns[best][1], spawns[best][2]),
                         1.0, spawns[best][1] - 2000, spawns[best][1] + 0.05);
    const bestScore = bestClear + (bestGround === -Infinity ? 1000 : 0);
    if (bestClear === -1 || score < bestScore) { bestClear = blocked; best = i; }
  }
  return best;
}

function stepPhysics(dt, index, camera) {
  const p = state.position;
  const forward = new THREE.Vector3(-Math.sin(state.camYaw), 0, -Math.cos(state.camYaw));
  const right = new THREE.Vector3(Math.cos(state.camYaw), 0, -Math.sin(state.camYaw));
  const move = new THREE.Vector3();
  if (state.keys.has('w')) move.add(forward);
  if (state.keys.has('s')) move.sub(forward);
  if (state.keys.has('d')) move.add(right);
  if (state.keys.has('a')) move.sub(right);
  const speed = state.keys.has('shift') ? PHYS.walkSpeed * 0.5 : PHYS.walkSpeed;
  if (move.lengthSq() > 0) move.normalize().multiplyScalar(speed * dt);

  // vertical
  state.velocity.y -= PHYS.gravity * dt;
  if (state.jumping && state.onGround) { state.velocity.y = PHYS.jumpPower; state.onGround = false; }
  state.jumping = false;

  let ny = p.y + state.velocity.y * dt;
  if (state.velocity.y <= 0) {
    // sweep the column the character passes through this step, so a fast fall
    // cannot tunnel through a floor
    const probe = new THREE.Vector3(p.x + move.x, p.y, p.z + move.z);
    const ground = groundTopInRange(index, probe, PHYS.characterRadius * 0.85, ny - 0.6, p.y + 0.05);
    if (ground !== -Infinity && ny <= ground) { ny = ground; state.velocity.y = 0; state.onGround = true; }
    else state.onGround = false;
  } else state.onGround = false;

  // horizontal with step-up
  const alreadyStuck = collides(index, new THREE.Vector3(p.x, ny, p.z),
                                PHYS.characterRadius, PHYS.characterHeight);
  const tryMove = (dx, dz) => {
    const cand = new THREE.Vector3(p.x + dx, ny, p.z + dz);
    const hit = collides(index, cand, PHYS.characterRadius, PHYS.characterHeight);
    if (!hit) { p.x = cand.x; p.z = cand.z; return; }
    // never "climb" while already overlapping geometry: that ratchets the
    // character upward frame after frame when a spawn is inside a building
    if (alreadyStuck) return;
    // step up over low ledges (Roblox characters climb steps)
    const stepY = hit.c[1] + hit.h[1];
    if (stepY - ny <= PHYS.stepHeight && stepY - ny > 0) {
      const stepped = new THREE.Vector3(cand.x, stepY + 0.02, cand.z);
      if (!collides(index, stepped, PHYS.characterRadius, PHYS.characterHeight)) {
        p.y = stepped.y; state.velocity.y = 0; state.onGround = true;
        p.x = cand.x; p.z = cand.z;
        return;
      }
    }
    // slide along each axis independently
    const candX = new THREE.Vector3(p.x + dx, ny, p.z);
    if (!collides(index, candX, PHYS.characterRadius, PHYS.characterHeight)) p.x = candX.x;
    const candZ = new THREE.Vector3(p.x, ny, p.z + dz);
    if (!collides(index, candZ, PHYS.characterRadius, PHYS.characterHeight)) p.z = candZ.z;
  };
  tryMove(move.x, move.z);
  p.y = ny;
  if (alreadyStuck) {
    const escape = findClearPosition(index, p, PHYS.characterRadius, PHYS.characterHeight);
    if (escape) state.position.copy(escape);
  }
  if (p.y < -220) respawn();   // fell out of the world (no baseplate)
  if (!state.onGround) {
    if (state.airborneSince === undefined) state.airborneSince = performance.now();
    else if (performance.now() - state.airborneSince > 4500) {
      // spawns authored in mid-air (or above the void) are resolved once, quietly
      respawn();
      state.airborneSince = performance.now();
    }
  } else state.airborneSince = undefined;
  return move.length() / Math.max(dt, 1e-4);
}

/** Find the nearest position where the character does not overlap any solid.
 *  Used for spawns authored inside structures and as a stuck-resolution escape. */
function findClearPosition(index, pos, radius, height) {
  if (!collides(index, pos, radius, height)) return pos.clone();
  const probe = new THREE.Vector3();
  const candidates = [];
  // Prefer a lateral exit at (or just above) the current level, so a spawn inside
  // a building ends up in the room rather than on the roof.
  for (let dy = 0; dy <= 14 && candidates.length < 60; dy += 1.5) {
    for (let r = 2; r <= 30 && candidates.length < 60; r += 2) {
      for (let a = 0; a < 12 && candidates.length < 60; a++) {
        const ang = (a / 12) * Math.PI * 2;
        probe.set(pos.x + Math.cos(ang) * r, pos.y + dy, pos.z + Math.sin(ang) * r);
        if (!collides(index, probe, radius, height)) candidates.push(probe.clone());
      }
    }
  }
  for (let dy = 15; dy <= 80 && candidates.length < 80; dy += 2) {
    probe.set(pos.x, pos.y + dy, pos.z);
    if (!collides(index, probe, radius, height)) candidates.push(probe.clone());
  }
  if (!candidates.length) return null;
  // Among the clear spots, prefer one that has solid ground beneath it: a spawn
  // inside a building should land in a room, never be pushed over the void edge.
  let best = null, bestDrop = Infinity;
  for (const c of candidates) {
    const ground = groundTopInRange(index, c, radius, c.y - 300, c.y + 0.05);
    const drop = ground === -Infinity ? Infinity : (c.y - ground);
    // closest lateral move wins ties; a short drop is fine (we fall onto the floor)
    if (drop < bestDrop) { bestDrop = drop; best = c; }
  }
  return best;
}

function respawn() {
  const g = state.geometry;
  if (g && g.spawns && g.spawns.pos.length) {
    const idx = state.spawnIndex >= 0 ? state.spawnIndex : 0;
    const s = g.spawns.pos[idx];
    const rot = g.rots[g.spawns.rot[idx]];
    state.position.set(s[0], s[1] + 0.5, s[2]);
    state.camYaw = Math.atan2(rot[2], rot[8]);      // face the spawn's -Z (look) direction
    if (state.collisionIndex) {
      state.camYaw = bestSpawnYaw(state.collisionIndex, state.position, state.camYaw);
    }
  } else {
    state.position.set(0, 20, 0);
  }
  // spawns that float above the void: stand on the place's real geometry instead
  if (state.collisionIndex) {
    const probe = new THREE.Vector3(state.position.x, state.position.y, state.position.z);
    const ground = groundTopInRange(state.collisionIndex, probe, PHYS.characterRadius * 0.85,
                                    probe.y - 2000, probe.y + 0.05);
    if (ground === -Infinity) {
      const stand = nearestStandable(state.collisionIndex, probe, PHYS.characterRadius,
                                     PHYS.characterHeight);
      if (stand) state.position.copy(stand);
    }
  }
  // a spawn authored inside a structure must not leave the character stuck
  if (state.collisionIndex) {
    const clear = findClearPosition(state.collisionIndex,
      new THREE.Vector3(state.position.x, state.position.y + 0.1, state.position.z),
      PHYS.characterRadius, PHYS.characterHeight);
    if (clear) state.position.copy(clear);
  }
  state.velocity.set(0, 0, 0);
  state.onGround = false;
  state.airborneSince = performance.now();
}

// ------------------------------------------------------------------ camera
function updateCamera(camera, character) {
  if (state.overview) {
    // Top-down overview of the whole place (BLOXEN helper for maps whose
    // spawn is inside a structure). Not a 2015 client feature.
    const g = state.geometry;
    const bounds = state.worldBounds;
    const cx = bounds ? (bounds.min[0] + bounds.max[0]) / 2 : state.position.x;
    const cz = bounds ? (bounds.min[2] + bounds.max[2]) / 2 : state.position.z;
    const span = bounds ? Math.max(bounds.max[0] - bounds.min[0],
                                   bounds.max[2] - bounds.min[2]) : 400;
    const height = Math.max(80, span * 0.75) * (state.overviewZoom || 1);
    camera.position.set(cx + height * 0.45, height, cz + height * 0.45);
    camera.lookAt(cx, 0, cz);
    return;
  }
  if (state.freeCam) {
    const f = new THREE.Vector3(-Math.sin(state.camYaw), 0, -Math.cos(state.camYaw));
    const r = new THREE.Vector3(Math.cos(state.camYaw), 0, -Math.sin(state.camYaw));
    const move = new THREE.Vector3();
    if (state.keys.has('w')) move.add(f);
    if (state.keys.has('s')) move.sub(f);
    if (state.keys.has('d')) move.add(r);
    if (state.keys.has('a')) move.sub(r);
    if (state.keys.has('space')) move.y += 1;
    if (state.keys.has('shift')) move.y -= 1;
    if (move.lengthSq() > 0) state.freeCamPos.add(move.normalize().multiplyScalar(1.4));
    camera.position.copy(state.freeCamPos);
    const dir = new THREE.Vector3(
      Math.cos(state.camPitch) * -Math.sin(state.camYaw),
      Math.sin(state.camPitch),
      Math.cos(state.camPitch) * -Math.cos(state.camYaw));
    camera.lookAt(state.freeCamPos.clone().add(dir));
    return;
  }
  const target = new THREE.Vector3(state.position.x, state.position.y + 3.2, state.position.z);
  const dir = new THREE.Vector3(
    Math.cos(state.camPitch) * Math.sin(state.camYaw),
    Math.sin(state.camPitch),
    Math.cos(state.camPitch) * Math.cos(state.camYaw));
  const desired = target.clone().add(dir.multiplyScalar(state.camDist));
  // pull the camera in when something is between it and the character
  if (state.collisionIndex) {
    const toCam = desired.clone().sub(target);
    const dist = toCam.length();
    const hit = rayHitDistance(state.collisionIndex, target, toCam.normalize(), dist, 0.4);
    if (hit < dist) desired.copy(target).add(toCam.multiplyScalar(Math.max(2.0, hit - 0.5)));
  }
  camera.position.lerp(desired, 0.35);
  camera.lookAt(target);
}

// -------------------------------------------------------------------- HUD
function renderPanels(geo, build) {
  const kv = el('blx-meta-table');
  const m = geo.meta || {}, s = geo.stats || {};
  const byContainer = Object.entries(s.parts_by_container || {})
    .map(([k, v]) => `${k}: ${v}`).join(', ');
  const rows = [
    ['game', RUNTIME.dataset.gameName],
    ['creator', RUNTIME.dataset.gameCreator],
    ['place file SHA-256', (m.place_sha256 || '').slice(0, 32) + '…'],
    ['format', m.format],
    ['target client build', m.target_build],
    ['instances parsed', s.instance_count],
    ['parts rendered', `${s.rendered_parts} of ${s.part_count} (${s.invisible_parts} invisible)`],
    ['spawn locations', s.spawn_count],
    ['parts by container', byContainer || 'Workspace'],
    ['outside Workspace', `${s.parts_outside_workspace || 0} (cloned into the world by the place's Lua at runtime; shown as saved)`],
    ['draw calls', build.drawCalls],
    ['scripts inventoried (not executed)', s.script_count],
    ['referenced assets', `${s.assets_referenced} (recovered ${s.assets_recovered}, missing ${s.assets_missing})`],
  ];
  kv.innerHTML = rows.map(([k, v]) => `<tr><td>${k}</td><td>${v ?? '—'}</td></tr>`).join('');

  const u = geo.unsupported || {};
  const nr = u.not_rendered_classes || {};
  const un = [];
  if (u.csg_unions) un.push(`CSG UnionOperations: ${u.csg_unions} — solid data not decoded, not substituted`);
  if (nr.MeshPart) un.push(`MeshPart: ${nr.MeshPart} — mesh assets missing, not substituted`);
  if (nr.SpecialMesh) un.push(`SpecialMesh: ${nr.SpecialMesh} — mesh assets missing`);
  un.push(`Terrain: ${u.terrain}`);
  un.push(`Scripts: ${u.scripts}`);
  un.push(`Decor (${s.decor_count} decals/textures): drawn only where the image asset is recovered`);
  el('blx-unsupported').innerHTML = un.map((t) => `<div class="blx-warn">• ${t}</div>`).join('');

  const fid = [
    `<div><span class="blx-badge">REAL</span> place geometry, colours, sizes, spawns, lighting</div>`,
    `<div><span class="blx-badge">REAL</span> R6 body dimensions + 2015 physics constants (16 / 50 / 196.2)</div>`,
    `<div><span class="blx-badge warn">RECONSTRUCTED</span> HUD chrome, stud/inlet textures, walk animation</div>`,
    `<div><span class="blx-badge warn">NOT RUN</span> the place's Lua (${(geo.stats || {}).script_count} scripts) — no game logic is simulated</div>`,
  ].join('');
  el('blx-fidelity').innerHTML = fid;
}

// ------------------------------------------------------------------ input
function bindInput(canvas, camera) {
  const rotKeys = { q: 0.05, e: -0.05 };
  window.addEventListener('keydown', (ev) => {
    const active = document.activeElement;
    if (active && active.id === 'blx-chat-input') {
      if (ev.key === 'Enter') {
        const text = active.value.trim();
        if (text) addChat(`${USERNAME}: ${text}`, true);
        active.value = '';
        active.blur();
        el('blx-chat').classList.remove('open');
      }
      return;
    }
    const k = ev.key.toLowerCase();
    if (k === 'enter') { el('blx-chat').classList.add('open'); el('blx-chat-input').focus(); ev.preventDefault(); return; }
    state.keys.add(k);
    if (['w', 'a', 's', 'd'].includes(k) && state.overview) state.overview = false;
    if (k === ' ') { state.jumping = true; ev.preventDefault(); }
    if (k === 'f') toggleFreeCam();
    if (k === 'o') toggleOverview();
    if (k === 'r') { respawn(); toast('Respawned at a SpawnLocation from the place file'); }
    if (k === 'm') el('blx-menu').classList.toggle('open');
  });
  window.addEventListener('keyup', (ev) => state.keys.delete(ev.key.toLowerCase()));
  window.addEventListener('blur', () => state.keys.clear());

  let dragging = false, lx = 0, ly = 0;
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  canvas.addEventListener('pointerdown', (e) => {
    if (state.overview) state.overview = false;
    if (e.button === 2 || e.button === 0) { dragging = true; lx = e.clientX; ly = e.clientY; canvas.setPointerCapture(e.pointerId); }
  });
  canvas.addEventListener('pointerup', (e) => { dragging = false; });
  canvas.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    state.camYaw -= (e.clientX - lx) * 0.006;
    state.camPitch = Math.max(-1.45, Math.min(1.45, state.camPitch - (e.clientY - ly) * 0.005));
    lx = e.clientX; ly = e.clientY;
  });
  canvas.addEventListener('wheel', (e) => {
    if (state.freeCam) return;
    state.camDist = Math.max(PHYS.zoomMin, Math.min(PHYS.zoomMax, state.camDist + Math.sign(e.deltaY) * 2));
    e.preventDefault();
  }, { passive: false });
}

function toggleOverview() {
  state.overview = !state.overview;
  if (state.overview && !state.worldBounds) {
    const pos = state.geometry.parts.pos;
    let min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < pos.length; i += 3) {
      for (let a = 0; a < 3; a++) {
        if (pos[i + a] < min[a]) min[a] = pos[i + a];
        if (pos[i + a] > max[a]) max[a] = pos[i + a];
      }
    }
    state.worldBounds = { min, max };
  }
  toast(state.overview ? 'Overview camera — press O or use WASD to return' : 'Third-person camera');
}

function toggleFreeCam() {
  state.freeCam = !state.freeCam;
  el('blx-opt-freecam').checked = state.freeCam;
  if (state.freeCam) state.freeCamPos = new THREE.Vector3(state.position.x, state.position.y + 12, state.position.z + 20);
  toast(state.freeCam ? 'Free camera on (noclip)' : 'Free camera off');
}

function addChat(text, local = false) {
  const log = el('blx-chat-log');
  const div = document.createElement('div');
  div.className = local ? '' : 'blx-chat-sys';
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

// ------------------------------------------------------------------- boot
async function boot() {
  document.body.classList.add('blx-playing');
  const canvas = el('blx-canvas');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.5, 8000);

  progress(6); status('fetching preserved place geometry…');
  let geo;
  try {
    const res = await fetch(`/api/place/${GAME_ID}/geometry`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    geo = await res.json();
  } catch (err) {
    status(`geometry unavailable: ${err.message}`);
    progress(100);
    return;
  }
  state.geometry = geo;
  progress(35); status(`decoded ${geo.stats.instance_count} instances — building world…`);
  await new Promise((r) => setTimeout(r, 30));

  // pull in the 2015 client's own surface/material/sky bitmaps BEFORE the world is built
  // so parts are textured with the real bitmaps from the first frame
  const clientTex = await loadClientTextures();
  if (clientTex && clientTex.manifest) {
    const mats = Object.keys(clientTex.manifest.materials || {}).length;
    status(`building world with the 2015 client's own assets `
           + `(${mats} material bitmaps, studs atlas ${clientTex.atlas ? 'ok' : 'MISSING'}, `
           + `default sky ${clientTex.sky ? 'ok' : 'MISSING'})…`);
  } else {
    status('building world (2015 client asset set not installed — surfaces left flat)…');
  }
  const build = buildWorld(geo);
  const sky = buildSky(geo, scene);
  scene.add(build.world);
  progress(70); status(`merging ${geo.stats.rendered_parts} parts into ${build.drawCalls} draw calls…`);

  const paletteRes = await fetch('/static/data/brickcolor.json');
  const paletteJson = await paletteRes.json();
  const namedPalette = {};
  for (const v of Object.values(paletteJson.colors)) namedPalette[v.name] = v.rgb;
  const character = buildCharacter(namedPalette);
  scene.add(character.group);

  let collisionIndex = makeCollisionIndex(build.collision);
  state.spawnIndex = bestSpawnIndex(geo, collisionIndex);
  state.collisionIndex = collisionIndex;
  respawn();
  state.freeCamPos = new THREE.Vector3(state.position.x, state.position.y + 12, state.position.z + 20);
  state.camYaw = state.camYaw || 0;
  renderPanels(geo, build);
  // diagnostics for tools/browser/probe_client.py (headless validation)
  window.__blx = { three: THREE.REVISION, trace: [],
    spawnPositions: (geo.spawns || {}).pos || [], stats: {
    drawCalls: build.drawCalls, buckets: build.bucketCount, rendered: build.rendered,
    colliders: build.collision.length, parts: geo.stats.part_count,
    containers: geo.stats.parts_by_container, spawns: geo.stats.spawn_count,
  } };
  progress(100); status('ready');

  bindInput(canvas, camera);
  addChat(`Place loaded: ${RUNTIME.dataset.gameName} — geometry from the preserved place file.`, true);
  addChat(`Lua scripts are inventoried but NOT executed in this runtime.`, true);
  addChat(`Controls: WASD move, Space jump, right-drag camera, M menu.`, true);

  el('blx-menu-btn').onclick = () => el('blx-menu').classList.toggle('open');
  el('blx-menu-close').onclick = () => el('blx-menu').classList.remove('open');
  el('blx-chat-btn').onclick = () => { el('blx-chat').classList.toggle('open'); if (el('blx-chat').classList.contains('open')) el('blx-chat-input').focus(); };
  el('blx-leave-btn').onclick = () => { window.location.href = `/games/${GAME_ID}`; };
  el('blx-opt-freecam').onchange = (e) => { if (e.target.checked !== state.freeCam) toggleFreeCam(); };
  el('blx-opt-containers').onchange = (e) => {
    state.showStored = e.target.checked;
    for (const m of build.storedMeshes) m.visible = state.showStored;
    toast(state.showStored ? 'Showing parts stored outside Workspace (as saved in the file)'
                           : 'Showing Workspace parts only');
  };
  el('blx-opt-studs').onchange = (e) => { state.studs = e.target.checked; rebuildHint(); };
  el('blx-opt-quality').onchange = (e) => {
    state.quality = e.target.value;
    renderer.setPixelRatio(state.quality === 'high' ? Math.min(window.devicePixelRatio, 2)
      : state.quality === 'low' ? 1 : Math.min(window.devicePixelRatio, 1.5));
    toast(`Graphics: ${state.quality}`);
  };
  el('blx-opt-wedge').onchange = (e) => {
    state.flipWedge = e.target.checked;
    const t0 = performance.now();
    const old = build.world;
    const rebuilt = buildWorld(geo, { flipWedge: state.flipWedge });
    scene.remove(old);
    disposeWorld(old);
    scene.add(rebuilt.world);
    build.world = rebuilt.world;
    build.storedMeshes = rebuilt.storedMeshes;
    build.drawCalls = rebuilt.drawCalls;
    collisionIndex = makeCollisionIndex(rebuilt.collision);
    state.collisionIndex = collisionIndex;
    state.spawnIndex = bestSpawnIndex(geo, collisionIndex);
    if (!state.showStored) for (const m of build.storedMeshes) m.visible = false;
    toast(`Wedge orientation: ${state.flipWedge ? 'flipped (variant B)' : 'default (variant A)'} `
      + `— rebuilt in ${(performance.now() - t0).toFixed(0)} ms`);
  };

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight, false);
  });

  // `last` starts unset: the first animation frame's timestamp can be earlier
  // than any performance.now() captured during boot, which would make dt negative
  // and launch the character upward instead of letting it fall.
  let last = null, fpsAcc = 0, fpsCount = 0, firstFrame = true;
  function frame(now) {
    if (firstFrame) {
      firstFrame = false;
      const l = el('blx-loading');
      if (l) { l.style.transition = 'opacity .35s'; l.style.opacity = '0';
               setTimeout(() => l.remove(), 400); }
    }
    if (last === null) last = now;
    const dt = Math.min(0.033, Math.max(0, (now - last) / 1000));
    last = now;
    const speed = state.freeCam ? 0 : stepPhysics(dt, collisionIndex, camera);
    if (!state.freeCam) {
      character.group.position.copy(state.position);
      character.group.rotation.y = state.camYaw + Math.PI;
      // The classic client hides the local character when the camera is pulled
      // in against geometry (first-person-ish view).
      const camDist = camera.position.distanceTo(state.position);
      character.group.visible = camDist > 6.5;
      animateCharacter(character.parts, speed, dt, !state.onGround);
      el('blx-speed').textContent = `${speed.toFixed(1)} studs/s`;
    }
    updateCamera(camera, character.group);
    // directional sun: only the direction matters, keep it centred on the viewer
    sky.sun.position.copy(camera.position).add(sky.sunOffset);
    sky.sun.target.position.copy(camera.position);
    renderer.render(scene, camera);
    if (window.__blx && window.__blx.trace && window.__blx.trace.length < 40) {
      window.__blx.trace.push([+now.toFixed(0), +state.position.y.toFixed(3),
        +state.velocity.y.toFixed(2), state.onGround ? 1 : 0, +dt.toFixed(4)]);
    }
    if (window.__blx) {
      window.__blx.diag = {
        character: [ +state.position.x.toFixed(2), +state.position.y.toFixed(2), +state.position.z.toFixed(2) ],
        camera: [ +camera.position.x.toFixed(2), +camera.position.y.toFixed(2), +camera.position.z.toFixed(2) ],
        camDistance: +camera.position.distanceTo(state.position).toFixed(2),
        onGround: state.onGround,
        spawnIndex: state.spawnIndex,
        spawnCount: ((geo.spawns && geo.spawns.pos) || []).length,
        cameraInsideSolid: !!collides(collisionIndex, camera.position, 0.05, 0.05),
        viewBlockedRatio: +viewBlockedRatio(collisionIndex, camera.position,
          camera.getWorldDirection(new THREE.Vector3())).toFixed(2),
        feetInsideSolid: !!collides(collisionIndex, state.position, PHYS.characterRadius * 0.9,
                                     PHYS.characterHeight),
      };
    }
    fpsAcc += dt; fpsCount++;
    if (fpsAcc > 0.5) { state.fps = fpsCount / fpsAcc; el('blx-fps').textContent = `${state.fps.toFixed(0)} fps`; fpsAcc = 0; fpsCount = 0; }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function rebuildHint() { toast('Surface pattern toggled (applies on next load)'); }

boot();
