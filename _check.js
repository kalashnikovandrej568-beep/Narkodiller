
// =============================================================
//  NEON DEFENSE вЂ” Synthwave Tower Defense Simulator
// =============================================================

const C = document.getElementById('c');
const X = C.getContext('2d');
const W = () => C.width;
const H = () => C.height;

function resize() { C.width = innerWidth; C.height = innerHeight; buildPath(); }
addEventListener('resize', resize);

const PI  = Math.PI;
const TAU = PI * 2;
const lerp = (a,b,t) => a + (b - a) * t;
const dst  = (a,b) => Math.hypot(b.x - a.x, b.y - a.y);
const clamp = (v,lo,hi) => Math.max(lo, Math.min(hi, v));

let gameSpeed = 1;
function toggleSpeed() {
  if(buffMods.speed4x){
    gameSpeed = gameSpeed===1?2:gameSpeed===2?3:gameSpeed===3?4:1;
  } else {
    gameSpeed = gameSpeed===1?2:gameSpeed===2?3:1;
  }
  document.getElementById('speed-btn').textContent = `SPEED: ${gameSpeed}x`;
}

// =============================================================
//  SYNTHWAVE MUSIC ENGINE  (Web Audio API)
// =============================================================
let actx, musicPlaying = false, musicGain;
const TEMPO = 110;
const BEAT = 60 / TEMPO;

const CHORDS = [
  [220.00, 261.63, 329.63],   // Am
  [174.61, 220.00, 261.63],   // F
  [261.63, 329.63, 392.00],   // C
  [196.00, 246.94, 293.66],   // G
];
const BASS = [110, 87.31, 130.81, 98];
const ARP_PAT = [1, 1.25, 1.5, 2, 1.5, 1.25, 1, 0.75];

let musicTimeout = null, currentBeat = 0;

function initAudio() {
  if (actx) return;
  actx = new (window.AudioContext || window.webkitAudioContext)();
  musicGain = actx.createGain();
  musicGain.gain.value = 0.30;

  // Reverb-like delay
  const delay = actx.createDelay();
  delay.delayTime.value = BEAT * 0.75;
  const fb = actx.createGain();
  fb.gain.value = 0.25;
  const wetGain = actx.createGain();
  wetGain.gain.value = 0.15;

  musicGain.connect(actx.destination);
  musicGain.connect(delay);
  delay.connect(fb);
  fb.connect(delay);
  delay.connect(wetGain);
  wetGain.connect(actx.destination);
}

function playNote(freq, start, dur, type = 'sine', vol = 0.08, dest) {
  if (!actx) return;
  dest = dest || musicGain;
  const osc = actx.createOscillator();
  const g   = actx.createGain();
  osc.type = type;
  osc.frequency.value = freq;

  // Smooth envelope
  g.gain.setValueAtTime(0, start);
  g.gain.linearRampToValueAtTime(vol, start + Math.min(0.03, dur * 0.1));
  g.gain.setValueAtTime(vol, start + dur * 0.7);
  g.gain.exponentialRampToValueAtTime(0.001, start + dur);
  osc.connect(g); g.connect(dest);
  osc.start(start); osc.stop(start + dur + 0.05);
}

function makeNoise(start, dur, vol, dest) {
  if (!actx) return;
  const len = Math.ceil(actx.sampleRate * dur);
  const buf = actx.createBuffer(1, len, actx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2);
  const src = actx.createBufferSource();
  const g = actx.createGain();
  // Hi-pass for hat sound
  const filt = actx.createBiquadFilter();
  filt.type = 'highpass';
  filt.frequency.value = 8000;
  src.buffer = buf;
  g.gain.setValueAtTime(vol, start);
  g.gain.exponentialRampToValueAtTime(0.001, start + dur);
  src.connect(filt); filt.connect(g); g.connect(dest || musicGain);
  src.start(start);
}

function scheduleBar() {
  if (!musicPlaying || !actx) return;
  const now = actx.currentTime + 0.05;
  const ci = currentBeat % 4;
  const chord = CHORDS[ci];
  const bass  = BASS[ci];
  const barLen = BEAT * 4;

  // --- Warm Pad ---
  chord.forEach(f => {
    playNote(f, now, barLen, 'sine', 0.022);
    playNote(f * 2.005, now, barLen, 'triangle', 0.008); // slight detune for warmth
  });

  // --- Sub Bass ---
  playNote(bass * 0.5, now, BEAT * 2, 'sine', 0.07);
  playNote(bass * 0.5, now + BEAT * 2, BEAT * 1.8, 'sine', 0.07);

  // --- Mid Bass (sawtooth, filtered feel via lower vol) ---
  playNote(bass, now, BEAT * 0.8, 'sawtooth', 0.035);
  playNote(bass, now + BEAT, BEAT * 0.8, 'sawtooth', 0.03);
  playNote(bass * 1.5, now + BEAT * 2, BEAT * 0.8, 'sawtooth', 0.03);
  playNote(bass, now + BEAT * 3, BEAT * 0.8, 'sawtooth', 0.035);

  // --- Arpeggio ---
  for (let i = 0; i < 16; i++) {
    const arpFreq = chord[1] * 2 * ARP_PAT[i % 8];
    const t = now + i * BEAT / 4;
    const vol = (i % 4 === 0) ? 0.022 : 0.014;
    playNote(arpFreq, t, BEAT / 5, 'square', vol);
  }

  // --- Hi-hats ---
  for (let i = 0; i < 8; i++) {
    const t = now + i * BEAT / 2;
    const vol = i % 2 === 0 ? 0.03 : 0.015;
    makeNoise(t, 0.04, vol);
  }

  // --- Kick ---
  for (const b of [0, 2]) {
    const t = now + b * BEAT;
    const osc = actx.createOscillator();
    const g = actx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(150, t);
    osc.frequency.exponentialRampToValueAtTime(35, t + 0.18);
    g.gain.setValueAtTime(0.14, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
    osc.connect(g); g.connect(musicGain);
    osc.start(t); osc.stop(t + 0.3);
  }

  // --- Snare (beat 2 & 4) ---
  for (const b of [1, 3]) {
    const t = now + b * BEAT;
    makeNoise(t, 0.1, 0.06);
    playNote(200, t, 0.08, 'triangle', 0.04);
  }

  currentBeat++;
  musicTimeout = setTimeout(scheduleBar, barLen * 1000 - 100);
}

function startMusic() {
  initAudio();
  if (actx.state === 'suspended') actx.resume();
  musicPlaying = true;
  currentBeat = 0;
  scheduleBar();
  document.getElementById('music-btn').textContent = 'в™Є MUSIC: ON';
}

function stopMusic() {
  musicPlaying = false;
  if (musicTimeout) clearTimeout(musicTimeout);
  document.getElementById('music-btn').textContent = 'в™Є MUSIC: OFF';
}

function toggleMusic() {
  musicPlaying ? stopMusic() : startMusic();
}

// --- SFX ---
function sfx(freq, dur, vol = 0.05, type = 'square') {
  if (!actx) return;
  const o = actx.createOscillator(), g = actx.createGain();
  o.type = type; o.frequency.value = freq;
  g.gain.setValueAtTime(vol, actx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + dur);
  o.connect(g); g.connect(actx.destination);
  o.start(); o.stop(actx.currentTime + dur);
}
function sfxPlace()   { sfx(600,.08,.05); sfx(900,.06,.04); }
function sfxShoot()   { sfx(700+Math.random()*300,.04,.025); }
function sfxBoom()    { sfx(80,.25,.07,'sawtooth'); }
function sfxKill()    { sfx(500,.05,.04); sfx(900,.04,.03,'sine'); }
function sfxLeak()    { sfx(150,.2,.06,'sawtooth'); }
function sfxUpgrade() { sfx(500,.06,.04); sfx(700,.06,.04); sfx(1000,.08,.04); }

// =============================================================
//  MAP PATH (smooth S-curve via Catmull-Rom)
// =============================================================
let PATH = [];

function buildPath() {
  C.width = innerWidth; C.height = innerHeight;
  const w = W(), h = H();
  const my = h * 0.48;

  const raw = [
    { x: -30,        y: my - 60 },
    { x: w * 0.08,   y: my - 60 },
    { x: w * 0.18,   y: my - 150 },
    { x: w * 0.30,   y: my - 150 },
    { x: w * 0.38,   y: my - 20 },
    { x: w * 0.34,   y: my + 100 },
    { x: w * 0.42,   y: my + 150 },
    { x: w * 0.54,   y: my + 150 },
    { x: w * 0.60,   y: my + 50 },
    { x: w * 0.56,   y: my - 50 },
    { x: w * 0.63,   y: my - 130 },
    { x: w * 0.76,   y: my - 130 },
    { x: w * 0.84,   y: my - 10 },
    { x: w * 0.88,   y: my + 70 },
    { x: w + 30,     y: my + 70 },
  ];

  PATH = [];
  const S = 14;
  for (let i = 0; i < raw.length - 1; i++) {
    const p0 = raw[Math.max(i-1,0)];
    const p1 = raw[i];
    const p2 = raw[Math.min(i+1,raw.length-1)];
    const p3 = raw[Math.min(i+2,raw.length-1)];
    for (let s = 0; s < S; s++) {
      const t = s/S, tt=t*t, ttt=tt*t;
      PATH.push({
        x: .5*((2*p1.x)+(-p0.x+p2.x)*t+(2*p0.x-5*p1.x+4*p2.x-p3.x)*tt+(-p0.x+3*p1.x-3*p2.x+p3.x)*ttt),
        y: .5*((2*p1.y)+(-p0.y+p2.y)*t+(2*p0.y-5*p1.y+4*p2.y-p3.y)*tt+(-p0.y+3*p1.y-3*p2.y+p3.y)*ttt),
      });
    }
  }
  PATH.push(raw[raw.length-1]);

  let d = 0; PATH[0]._d = 0;
  for (let i = 1; i < PATH.length; i++) {
    d += dst(PATH[i-1],PATH[i]);
    PATH[i]._d = d;
  }
  PATH._totalDist = d;
}

function pathPos(p) {
  const td = p * PATH._totalDist;
  for (let i = 1; i < PATH.length; i++) {
    if (PATH[i]._d >= td) {
      const seg = PATH[i]._d - PATH[i-1]._d;
      const t = seg > 0 ? (td - PATH[i-1]._d)/seg : 0;
      return { x: lerp(PATH[i-1].x,PATH[i].x,t), y: lerp(PATH[i-1].y,PATH[i].y,t) };
    }
  }
  return {...PATH[PATH.length-1]};
}

// =============================================================
//  TOWER DEFINITIONS (18 towers in 6 lines)
// =============================================================
const TDEFS = [
  // === KINETIC LINE (0-2) ===
  { name:'BLASTER',  cost:50,  color:'#00ffcc', range:130, rate:28, dmg:12, splash:0,  slow:0,   beam:false, line:0,
    upgrades:[{cost:35,dmg:18,range:140,rate:24},{cost:70,dmg:28,range:155,rate:20},{cost:130,dmg:42,range:175,rate:16}]},
  { name:'GATLING',  cost:65,  color:'#00ffcc', range:120, rate:12, dmg:5,  splash:0,  slow:0,   beam:false, line:0,
    upgrades:[{cost:40,dmg:8,range:130,rate:10},{cost:80,dmg:12,range:140,rate:8},{cost:150,dmg:17,range:150,rate:6}]},
  { name:'SNIPER',   cost:100, color:'#00ffcc', range:220, rate:80, dmg:55, splash:0,  slow:0,   beam:false, line:0,
    upgrades:[{cost:60,dmg:85,range:240,rate:72},{cost:120,dmg:130,range:260,rate:64},{cost:200,dmg:200,range:280,rate:55}]},
  // === EXPLOSIVE LINE (3-5) ===
  { name:'CANNON',   cost:100, color:'#ff6600', range:115, rate:65, dmg:30, splash:55, slow:0,   beam:false, line:1,
    upgrades:[{cost:60,dmg:48,range:125,rate:60,splash:65},{cost:120,dmg:72,range:140,rate:52,splash:80},{cost:200,dmg:110,range:155,rate:45,splash:100}]},
  { name:'MORTAR',   cost:85,  color:'#ff6600', range:160, rate:100,dmg:40, splash:80, slow:0,   beam:false, line:1,
    upgrades:[{cost:50,dmg:65,splash:95,rate:90},{cost:100,dmg:100,splash:115,rate:80},{cost:170,dmg:150,splash:140,rate:70}]},
  { name:'ROCKET',   cost:140, color:'#ff6600', range:150, rate:55, dmg:35, splash:40, slow:0,   beam:false, homing:true, line:1,
    upgrades:[{cost:70,dmg:55,range:165,splash:50},{cost:140,dmg:80,range:180,splash:60},{cost:230,dmg:120,range:200,splash:75}]},
  // === ICE LINE (6-8) ===
  { name:'CRYO',     cost:75,  color:'#00aaff', range:125, rate:35, dmg:5,  splash:0,  slow:0.5, beam:false, line:2,
    upgrades:[{cost:45,dmg:8,range:135,slow:.6},{cost:90,dmg:12,range:150,slow:.72},{cost:160,dmg:18,range:170,slow:.88}]},
  { name:'FROSTBITE',cost:90,  color:'#00aaff', range:130, rate:30, dmg:14, splash:0,  slow:0.6, beam:false, line:2,
    upgrades:[{cost:55,dmg:22,slow:.7,range:140},{cost:110,dmg:32,slow:.8,range:155},{cost:180,dmg:45,slow:.9,range:170}]},
  { name:'BLIZZARD', cost:130, color:'#00aaff', range:140, rate:45, dmg:8,  splash:70, slow:0.65,beam:false, line:2,
    upgrades:[{cost:65,dmg:14,splash:85,slow:.75},{cost:130,dmg:22,splash:100,slow:.85},{cost:210,dmg:32,splash:120,slow:.95}]},
  // === ENERGY LINE (9-11) ===
  { name:'LASER',    cost:125, color:'#ff0066', range:160, rate:2,  dmg:.5, splash:0,  slow:0,   beam:true,  line:3,
    upgrades:[{cost:70,dmg:.8,range:175},{cost:140,dmg:1.3,range:195},{cost:240,dmg:2.0,range:220}]},
  { name:'PLASMA',   cost:110, color:'#ff0066', range:140, rate:22, dmg:18, splash:0,  slow:0,   beam:false, dot:3, line:3,
    upgrades:[{cost:60,dmg:28,rate:18,dot:5},{cost:120,dmg:42,rate:15,dot:8},{cost:200,dmg:60,rate:12,dot:12}]},
  { name:'DISRUPTOR',cost:170, color:'#ff0066', range:150, rate:40, dmg:25, splash:0,  slow:0,   beam:false, shieldBreak:true, line:3,
    upgrades:[{cost:80,dmg:40,range:165},{cost:160,dmg:60,range:180},{cost:260,dmg:90,range:200}]},
  // === TECH LINE (12-14) ===
  { name:'TESLA',    cost:115, color:'#ffcc00', range:130, rate:45, dmg:15, splash:0,  slow:0,   beam:false, chain:3, line:4,
    upgrades:[{cost:65,dmg:25,chain:4,range:140},{cost:130,dmg:38,chain:5,range:155},{cost:220,dmg:55,chain:6,range:170}]},
  { name:'RAILGUN',  cost:200, color:'#ffcc00', range:230, rate:95, dmg:70, splash:0,  slow:0,   beam:false, pierce:true, line:4,
    upgrades:[{cost:110,dmg:105,range:250,rate:85},{cost:190,dmg:160,range:270,rate:75},{cost:320,dmg:250,range:300,rate:65}]},
  { name:'EMP',      cost:250, color:'#ffcc00', range:160, rate:120,dmg:20, splash:90, slow:0,   beam:false, stun:60, shieldBreak:true, line:4,
    upgrades:[{cost:120,dmg:35,splash:110,stun:80},{cost:200,dmg:55,splash:130,stun:100},{cost:340,dmg:80,splash:155,stun:120}]},
  // === TOXIC LINE (15-17) ===
  { name:'ACID',     cost:70,  color:'#44ff00', range:120, rate:40, dmg:8,  splash:0,  slow:0,   beam:false, dot:6,  line:5,
    upgrades:[{cost:40,dmg:12,dot:9,range:130},{cost:85,dmg:18,dot:14,range:145},{cost:150,dmg:25,dot:20,range:160}]},
  { name:'PLAGUE',   cost:120, color:'#44ff00', range:130, rate:50, dmg:6,  splash:60, slow:0,   beam:false, dot:5,  line:5,
    upgrades:[{cost:60,dmg:10,dot:8,splash:75},{cost:120,dmg:16,dot:12,splash:90},{cost:200,dmg:24,dot:18,splash:110}]},
  { name:'VENOM',    cost:180, color:'#44ff00', range:140, rate:35, dmg:4,  splash:0,  slow:0.2, beam:false, dot:10, line:5,
    upgrades:[{cost:80,dmg:7,dot:15,slow:.3},{cost:160,dmg:11,dot:22,slow:.4},{cost:270,dmg:16,dot:30,slow:.5}]},
  // === ECONOMY LINE (18-20) ===
  { name:'MINT',     cost:120, color:'#ffd700', range:0,  rate:0,  dmg:0,  splash:0,  slow:0,   beam:false, farm:8,  line:6,
    upgrades:[{cost:80,farm:14},{cost:160,farm:22},{cost:300,farm:35}]},
  { name:'BANK',     cost:200, color:'#ffd700', range:0,  rate:0,  dmg:0,  splash:0,  slow:0,   beam:false, farm:18, line:6,
    upgrades:[{cost:120,farm:30},{cost:220,farm:48},{cost:400,farm:70}]},
  { name:'MEGACORP', cost:400, color:'#ffd700', range:0,  rate:0,  dmg:0,  splash:0,  slow:0,   beam:false, farm:40, line:6,
    upgrades:[{cost:200,farm:65},{cost:350,farm:100},{cost:600,farm:160}]},
];

const TOWER_ICONS = ['\u2b21','\u25ce','\u2295', '\u2738','\u25c9','\u2605', '\u2744','\u273b','\u2748', '\u26a1','\u25c8','\u25c6', '\u2726','\u27d0','\u25c7', '\u2623','\u229b','\u2297', '\u2b26','\u2b27','\u2b20'];
const TOWER_DESC = [
  'Fast shooter','Rapid fire','Long range sniper',
  'Splash damage','Large area mortar','Homing rockets',
  'Slows enemies','Strong slow+dmg','Area freeze',
  'Continuous beam','Burn damage','Shield breaker',
  'Chain lightning','Piercing rail','Area EMP stun',
  'Acid DoT','Spreading plague','Stacking venom',
  'Gold per wave','Big income','Massive profits'
];

// =============================================================
//  TECH TREE SYSTEM
// =============================================================
let researchPoints = 0;
let unlockedTowers = new Set([0, 3, 6]); // Blaster, Cannon, Cryo start unlocked
let waveRPGiven = false;

const TECH_LINES = [
  { name:'KINETIC',   color:'#00ffcc', towers:[0,1,2], desc:'Fast projectiles' },
  { name:'EXPLOSIVE', color:'#ff6600', towers:[3,4,5], desc:'Area damage' },
  { name:'ICE',       color:'#00aaff', towers:[6,7,8], desc:'Slow & freeze' },
  { name:'ENERGY',    color:'#ff0066', towers:[9,10,11],desc:'Beams & energy' },
  { name:'TECH',      color:'#ffcc00', towers:[12,13,14],desc:'Advanced tech' },
  { name:'TOXIC',     color:'#44ff00', towers:[15,16,17],desc:'Poison & DoT' },
  { name:'ECONOMY',   color:'#ffd700', towers:[18,19,20],desc:'Gold income' },
];
const RESEARCH_COST = [0,1,2, 0,1,2, 0,1,2, 2,2,3, 2,3,3, 3,3,4, 1,2,3];

function canResearch(idx) {
  if (unlockedTowers.has(idx)) return false;
  const cost = RESEARCH_COST[idx];
  if (cost === 0 || researchPoints < cost) return false;
  for (const ln of TECH_LINES) {
    const pos = ln.towers.indexOf(idx);
    if (pos < 0) continue;
    if (pos === 0) return true;
    return unlockedTowers.has(ln.towers[pos - 1]);
  }
  return false;
}

function researchTower(idx) {
  if (!canResearch(idx)) return;
  researchPoints -= RESEARCH_COST[idx];
  unlockedTowers.add(idx);
  buildTowerBar();
  renderTechTree();
  updateRPDisplay();
  sfxUpgrade();
  addFloat(W()/2, H()/2, `UNLOCKED: ${TDEFS[idx].name}`, TDEFS[idx].color);
}

function buildTowerBar() {
  const bar = document.getElementById('tower-bar');
  bar.innerHTML = '';
  [...unlockedTowers].sort((a,b) => a-b).forEach(i => {
    const def = TDEFS[i];
    const card = document.createElement('div');
    card.className = 'tower-card';
    card.dataset.idx = String(i);
    card.onclick = () => selectTower(i);
    const actualCost = Math.round(def.cost*(1-buffMods.towerDiscount));
    card.innerHTML = `<div class="icon" style="color:${def.color}">${TOWER_ICONS[i]}</div><div class="tname">${def.name}</div><div class="cost">${actualCost} G</div>`;
    bar.appendChild(card);
  });
}

function openTechTree() { renderTechTree(); document.getElementById('tech-overlay').style.display='flex'; }
function closeTechTree() { document.getElementById('tech-overlay').style.display='none'; }

function renderTechTree() {
  const c = document.getElementById('tech-lines-container');
  c.innerHTML = '';
  TECH_LINES.forEach(ln => {
    const div = document.createElement('div');
    div.className = 'tech-line';
    let h = `<div class="tech-line-title" style="color:${ln.color}">${ln.name}</div>`;
    ln.towers.forEach((idx, pos) => {
      const def = TDEFS[idx];
      const unlocked = unlockedTowers.has(idx);
      const avail = canResearch(idx);
      const cls = unlocked ? 'unlocked' : avail ? 'available' : 'locked';
      if (pos > 0) h += `<div class="tech-conn">\u2502</div>`;
      h += `<div class="tech-node ${cls}" style="color:${ln.color}" onclick="researchTower(${idx})">`;
      h += `<div class="tn-name">${TOWER_ICONS[idx]} ${def.name}</div>`;
      h += `<div class="tn-desc">${TOWER_DESC[idx]}</div>`;
      h += unlocked ? `<div class="tn-cost" style="color:#00ff88">\u2713 UNLOCKED</div>` :
        `<div class="tn-cost">${RESEARCH_COST[idx]} RP${avail?' \u2014 CLICK':''}  </div>`;
      h += `</div>`;
    });
    div.innerHTML = h;
    c.appendChild(div);
  });
}

function updateRPDisplay() {
  document.getElementById('rp-display').textContent = `RP: ${researchPoints}`;
}

// =============================================================
//  CASINO & BUFF SYSTEM
// =============================================================
let casinoCoins = 0;
let ownedBuffs = new Set();
let activeBuffs = [];
let slotSpinning = false;
let abilities = [null, null]; // player abilities (Q, W)
let abilityCooldowns = [0, 0];

// Global buff modifiers
let buffMods = {
  dmgMul: 1, rateMul: 1, rangeMul: 1, splashMul: 1,
  slowMul: 1, dotMul: 1, chainAdd: 0, farmMul: 1,
  goldPerKill: 0, extraLives: 0, bonusGoldWave: 0,
  critChance: 0, critMul: 1.5, stunChance: 0,
  pierce: false, lifesteal: 0, aoeOnKill: 0,
  towerDiscount: 0, upgradeDiscount: 0,
  enemySlow: 0, startGold: 0,
  speed4x: false, autoWave: false,
};

const SLOT_SYMBOLS = ['рџ’Ћ','рџ”Ґ','вљЎ','вќ„пёЏ','в пёЏ','рџЋЇ','рџ’°','рџЊџ'];

const ALL_BUFFS = [
  // ===== COMMON (0-15) вЂ” simple stat buffs =====
  {id:0, name:'HARDENED ROUNDS', desc:'All towers deal +15% damage', rarity:'common', icon:'рџ”«',
    apply(){buffMods.dmgMul+=.15;}},
  {id:1, name:'RAPID FIRE', desc:'All towers fire 12% faster', rarity:'common', icon:'вљЎ',
    apply(){buffMods.rateMul*=.88;}},
  {id:2, name:'EAGLE EYE', desc:'All towers get +12% range', rarity:'common', icon:'рџ”­',
    apply(){buffMods.rangeMul+=.12;}},
  {id:3, name:'WIDER BLAST', desc:'Splash radius +20%', rarity:'common', icon:'рџ’Ґ',
    apply(){buffMods.splashMul+=.20;}},
  {id:4, name:'DEEP FREEZE', desc:'Slow effects +25% stronger', rarity:'common', icon:'вќ„пёЏ',
    apply(){buffMods.slowMul+=.25;}},
  {id:5, name:'ACID BATH', desc:'DoT damage +30%', rarity:'common', icon:'в пёЏ',
    apply(){buffMods.dotMul+=.30;}},
  {id:6, name:'BOUNTY HUNTER', desc:'+2 gold per enemy killed', rarity:'common', icon:'рџ’°',
    apply(){buffMods.goldPerKill+=2;}},
  {id:7, name:'FORTIFY', desc:'+5 extra lives', rarity:'common', icon:'рџ›ЎпёЏ',
    apply(){buffMods.extraLives+=5; lives+=5;}},
  {id:8, name:'WAR BONDS', desc:'+30 bonus gold per wave', rarity:'common', icon:'рџ“њ',
    apply(){buffMods.bonusGoldWave+=30;}},
  {id:9, name:'MARKET GROWTH', desc:'Farm income +25%', rarity:'common', icon:'рџ“€',
    apply(){buffMods.farmMul+=.25;}},
  {id:10, name:'CHAIN EXTENDER', desc:'Chain lightning hits +1 target', rarity:'common', icon:'в›“пёЏ',
    apply(){buffMods.chainAdd+=1;}},
  {id:11, name:'BARGAIN BIN', desc:'Towers cost 10% less', rarity:'common', icon:'рџЏ·пёЏ',
    apply(){buffMods.towerDiscount+=.10;}},
  {id:12, name:'FIELD TRAINING', desc:'Upgrades cost 12% less', rarity:'common', icon:'рџ“љ',
    apply(){buffMods.upgradeDiscount+=.12;}},
  {id:13, name:'HEADWIND', desc:'All enemies permanently 8% slower', rarity:'common', icon:'рџЊ¬пёЏ',
    apply(){buffMods.enemySlow+=.08;}},
  {id:14, name:'SIGNING BONUS', desc:'+100 gold immediately', rarity:'common', icon:'рџ’µ',
    apply(){gold+=100;}},
  {id:15, name:'SNIPER SCOPE', desc:'Sniper towers +40% damage, +30 range', rarity:'common', icon:'рџЋЇ',
    apply(){towers.forEach(t=>{if(t.type===2){t.dmg*=1.4;t.range+=30;}});}},

  // ===== RARE (16-31) вЂ” mechanic tweaks =====
  {id:16, name:'CRITICAL SYSTEMS', desc:'10% chance for towers to deal 2x damage', rarity:'rare', icon:'рџ’ў',
    apply(){buffMods.critChance+=.10; buffMods.critMul=2;}},
  {id:17, name:'STUN ROUNDS', desc:'All projectiles have 8% chance to stun 1s', rarity:'rare', icon:'рџ’«',
    apply(){buffMods.stunChance+=.08;}},
  {id:18, name:'ARMOR PIERCING', desc:'Attacks ignore 30% of enemy armor', rarity:'rare', icon:'рџ—ЎпёЏ',
    apply(){buffMods.armorPierce=.30;}},
  {id:19, name:'CHAIN REACTION', desc:'Enemies explode on death dealing 15% max HP as area dmg', rarity:'rare', icon:'рџ”Ґ',
    apply(){buffMods.aoeOnKill=.15;}},
  {id:20, name:'VAMPIRIC TOWERS', desc:'Towers heal +1 life per 50 kills', rarity:'rare', icon:'рџ§›',
    apply(){buffMods.lifesteal+=.02;}},
  {id:21, name:'OVERDRIVE', desc:'Unlock 4x game speed option', rarity:'rare', icon:'вЏ©',
    apply(){buffMods.speed4x=true;}},
  {id:22, name:'AUTO-DEPLOY', desc:'Waves auto-start after 5 seconds idle', rarity:'rare', icon:'рџ¤–',
    apply(){buffMods.autoWave=true;}},
  {id:23, name:'SPLITTER BANE', desc:'Splitter enemies spawn 0 minis on death', rarity:'rare', icon:'вњ‚пёЏ',
    apply(){buffMods.noSplit=true;}},
  {id:24, name:'STEALTH SCANNER', desc:'All stealth enemies are permanently visible', rarity:'rare', icon:'рџ“Ў',
    apply(){buffMods.revealStealth=true;}},
  {id:25, name:'DOUBLE MINT', desc:'Farm towers generate income twice per wave', rarity:'rare', icon:'рџЏ¦',
    apply(){buffMods.doubleFarm=true;}},
  {id:26, name:'OVERKILL', desc:'Excess damage on kills is dealt to nearest enemy', rarity:'rare', icon:'вљ”пёЏ',
    apply(){buffMods.overkill=true;}},
  {id:27, name:'MULTISHOT', desc:'Gatling towers fire 2 projectiles per shot', rarity:'rare', icon:'рџ”‚',
    apply(){buffMods.multishot=true;}},
  {id:28, name:'CRYO CASCADE', desc:'Frozen enemies shatter & slow neighbors on death', rarity:'rare', icon:'рџ§Љ',
    apply(){buffMods.cryoCascade=true;}},
  {id:29, name:'RESEARCH GRANT', desc:'+2 research points immediately', rarity:'rare', icon:'рџ§¬',
    apply(){researchPoints+=2; updateRPDisplay();}},
  {id:30, name:'SHIELD BREAKER', desc:'All towers strip 50% more shield', rarity:'rare', icon:'рџ”Ё',
    apply(){buffMods.shieldBreakMul=1.5;}},
  {id:31, name:'RICOCHET', desc:'Non-splash projectiles bounce to 1 nearby enemy', rarity:'rare', icon:'рџЄѓ',
    apply(){buffMods.ricochet=true;}},

  // ===== EPIC (32-43) вЂ” major mechanic changes =====
  {id:32, name:'FREEZE BLAST', desc:'ABILITY [Q]: Freeze ALL enemies for 3s. Cooldown: 30s', rarity:'epic', icon:'рџҐ¶',
    apply(){
      abilities[0]={name:'FREEZE',icon:'рџҐ¶',cooldown:1800,dur:180,action(){
        enemies.forEach(e=>{if(!e.dead)e.stunTimer=Math.max(e.stunTimer,180);});
        spawnP(W()/2,H()/2,30,'#00aaff',6,30,4);
        addFloat(W()/2,H()/2,'вќ„пёЏ FREEZE BLAST!','#00aaff');
      }};
      updateAbilityUI();
    }},
  {id:33, name:'NAPALM STRIKE', desc:'ABILITY [Q]: Burn all enemies for 5s. Cooldown: 25s', rarity:'epic', icon:'рџ”Ґ',
    apply(){
      abilities[0]={name:'NAPALM',icon:'рџ”Ґ',cooldown:1500,dur:0,action(){
        enemies.forEach(e=>{if(!e.dead){e.dotDmg=Math.max(e.dotDmg,3);e.dotTimer=300;}});
        spawnP(W()/2,H()/2,25,'#ff6600',5,25,3);
        addFloat(W()/2,H()/2,'рџ”Ґ NAPALM!','#ff6600');
      }};
      updateAbilityUI();
    }},
  {id:34, name:'GOLD RUSH', desc:'ABILITY [W]: Double gold from kills for 10s. Cooldown: 45s', rarity:'epic', icon:'рџ’°',
    apply(){
      abilities[1]={name:'GOLD RUSH',icon:'рџ’°',cooldown:2700,dur:600,action(){
        buffMods._goldRushTimer=600;
        addFloat(W()/2,H()/2,'рџ’° GOLD RUSH!','#ffd700');
      }};
      updateAbilityUI();
    }},
  {id:35, name:'EMP PULSE', desc:'ABILITY [W]: Stun + remove shields from all enemies. CD: 35s', rarity:'epic', icon:'вљЎ',
    apply(){
      abilities[1]={name:'EMP PULSE',icon:'вљЎ',cooldown:2100,dur:0,action(){
        enemies.forEach(e=>{if(!e.dead){e.stunTimer=Math.max(e.stunTimer,120);e.shield=0;}});
        spawnP(W()/2,H()/2,30,'#ffcc00',6,30,4);
        addFloat(W()/2,H()/2,'вљЎ EMP PULSE!','#ffcc00');
      }};
      updateAbilityUI();
    }},
  {id:36, name:'OVERCHARGE', desc:'All towers deal 2x damage but fire 30% slower for 15s per wave', rarity:'epic', icon:'рџ”‹',
    apply(){buffMods.overcharge=true;}},
  {id:37, name:'ECONOMY ENGINE', desc:'Every 5th wave gives +1 casino coin', rarity:'epic', icon:'рџЋ°',
    apply(){buffMods.extraCoinEvery5=true;}},
  {id:38, name:'TOWER FRENZY', desc:'When enemies < 3, all towers fire 50% faster', rarity:'epic', icon:'рџ¤',
    apply(){buffMods.frenzy=true;}},
  {id:39, name:'POISON CLOUD', desc:'Enemies that die to DoT leave a poison zone for 5s', rarity:'epic', icon:'вЃпёЏ',
    apply(){buffMods.poisonCloud=true;}},
  {id:40, name:'MAGNETIC FIELD', desc:'Enemies move 15% slower when near any tower', rarity:'epic', icon:'рџ§І',
    apply(){buffMods.magneticField=true;}},
  {id:41, name:'CRITICAL MASS', desc:'Crits now deal 3x instead of 2x', rarity:'epic', icon:'вўпёЏ',
    apply(){buffMods.critMul=3;}},
  {id:42, name:'RECYCLER', desc:'Selling towers refunds 90% instead of 60%', rarity:'epic', icon:'в™»пёЏ',
    apply(){buffMods.sellRefund=.90;}},
  {id:43, name:'TOWER SYNERGY', desc:'Towers near other towers (< 80px) get +20% damage', rarity:'epic', icon:'рџ¤ќ',
    apply(){buffMods.synergy=true;}},

  // ===== LEGENDARY (44-49) вЂ” game-changing =====
  {id:44, name:'CHRONO WARP', desc:'ABILITY [Q]: Rewind all enemies by 2 seconds. CD: 40s', rarity:'legendary', icon:'вЏЄ',
    apply(){
      abilities[0]={name:'CHRONO',icon:'вЏЄ',cooldown:2400,dur:0,action(){
        enemies.forEach(e=>{if(!e.dead){e.progress=Math.max(0,e.progress-e.speed*120);const pos=pathPos(clamp(e.progress,0,1));e.x=pos.x;e.y=pos.y;}});
        spawnP(W()/2,H()/2,40,'#00ffcc',8,40,5);
        addFloat(W()/2,H()/2,'вЏЄ TIME WARP!','#00ffcc');
      }};
      updateAbilityUI();
    }},
  {id:45, name:'DEATH RAY', desc:'ABILITY [W]: Destroy the enemy with highest HP. CD: 60s', rarity:'legendary', icon:'рџ’Ђ',
    apply(){
      abilities[1]={name:'DEATH RAY',icon:'рџ’Ђ',cooldown:3600,dur:0,action(){
        let target=null,maxHp=0;
        enemies.forEach(e=>{if(!e.dead&&e.hp>maxHp){maxHp=e.hp;target=e;}});
        if(target){target.hp=0;spawnP(target.x,target.y,20,'#ff0044',6,30,5);addFloat(target.x,target.y,'рџ’Ђ ELIMINATED','#ff0044');}
      }};
      updateAbilityUI();
    }},
  {id:46, name:'GOLDEN AGE', desc:'All farms produce 100% more. Start each wave with +50 gold', rarity:'legendary', icon:'рџ‘‘',
    apply(){buffMods.farmMul+=1.0;buffMods.bonusGoldWave+=50;}},
  {id:47, name:'OMEGA CRIT', desc:'25% crit chance, crits deal 4x damage', rarity:'legendary', icon:'в­ђ',
    apply(){buffMods.critChance=.25;buffMods.critMul=4;}},
  {id:48, name:'IMMORTAL TOWERS', desc:'Tower upgrades cost nothing. Cannot buy new towers for 3 waves', rarity:'legendary', icon:'в™ѕпёЏ',
    apply(){buffMods.freeUpgrades=true;buffMods.buildBanWaves=3;}},
  {id:49, name:'SINGULARITY', desc:'ABILITY [Q]: Pull all enemies to map center & stun 2s. CD: 50s', rarity:'legendary', icon:'рџЊЂ',
    apply(){
      abilities[0]={name:'SINGULARITY',icon:'рџЊЂ',cooldown:3000,dur:0,action(){
        const cx=W()/2,cy=H()/2;
        enemies.forEach(e=>{if(!e.dead){
          e.x+=(cx-e.x)*.6; e.y+=(cy-e.y)*.6;
          e.stunTimer=Math.max(e.stunTimer,120);
        }});
        spawnP(cx,cy,40,'#ff00ff',8,40,6);
        addFloat(cx,cy,'рџЊЂ SINGULARITY!','#ff00ff');
      }};
      updateAbilityUI();
    }},
];

// Casino functions
function updateCoinDisplay(){
  const d=document.getElementById('coin-display');
  const b=document.getElementById('casino-btn');
  d.textContent=`COINS: ${casinoCoins}`;
  d.style.display=casinoCoins>0?'block':'none';
  b.style.display=casinoCoins>0?'block':'none';
  const cd=document.getElementById('casino-coins-display');
  if(cd) cd.textContent=`COINS: ${casinoCoins}`;
}

function openCasino(){
  if(casinoCoins<=0)return;
  document.getElementById('casino-overlay').style.display='flex';
  document.getElementById('buff-choices').style.display='none';
  document.getElementById('spin-btn').disabled=false;
  document.getElementById('reel1').textContent='?';
  document.getElementById('reel2').textContent='?';
  document.getElementById('reel3').textContent='?';
  updateCoinDisplay();
}
function closeCasino(){ document.getElementById('casino-overlay').style.display='none'; }

function spinSlots(){
  if(slotSpinning||casinoCoins<=0) return;
  casinoCoins--;
  updateCoinDisplay();
  slotSpinning=true;
  document.getElementById('spin-btn').disabled=true;
  document.getElementById('buff-choices').style.display='none';
  sfx(800,.06,.05); sfx(1000,.04,.04);

  // Animate reels
  const reels=[document.getElementById('reel1'),document.getElementById('reel2'),document.getElementById('reel3')];
  reels.forEach(r=>r.classList.add('spinning'));
  let spinCount=0;
  const spinInterval=setInterval(()=>{
    reels.forEach(r=>r.textContent=SLOT_SYMBOLS[Math.floor(Math.random()*SLOT_SYMBOLS.length)]);
    spinCount++;
    if(spinCount>20){
      clearInterval(spinInterval);
      reels.forEach((r,i)=>{
        setTimeout(()=>{
          r.classList.remove('spinning');
          r.textContent=SLOT_SYMBOLS[Math.floor(Math.random()*SLOT_SYMBOLS.length)];
          sfx(600+i*200,.05,.04);
          if(i===2) showBuffChoices();
        }, i*300);
      });
    }
  },80);
}

function showBuffChoices(){
  slotSpinning=false;
  // Pick 3 unique buffs not already owned
  const available=ALL_BUFFS.filter(b=>!ownedBuffs.has(b.id));
  if(available.length===0){
    addFloat(W()/2,H()/2,'ALL BUFFS OWNED!','#ffd700');
    closeCasino();
    return;
  }
  // Weighted random: legendaries rarer
  const weighted=[];
  available.forEach(b=>{
    const w=b.rarity==='common'?10:b.rarity==='rare'?6:b.rarity==='epic'?3:1;
    for(let i=0;i<w;i++) weighted.push(b);
  });
  const picks=[];
  const usedIds=new Set();
  while(picks.length<3 && picks.length<available.length){
    const b=weighted[Math.floor(Math.random()*weighted.length)];
    if(!usedIds.has(b.id)){usedIds.add(b.id);picks.push(b);}
  }

  const container=document.getElementById('buff-choices');
  container.innerHTML='';
  container.style.display='flex';
  picks.forEach(b=>{
    const card=document.createElement('div');
    card.className='buff-card';
    card.innerHTML=`<div class="bc-icon">${b.icon}</div><div class="bc-name">${b.name}</div><div class="bc-desc">${b.desc}</div><div class="bc-rarity ${b.rarity}">${b.rarity.toUpperCase()}</div>`;
    card.onclick=()=>selectBuff(b);
    container.appendChild(card);
  });
}

function selectBuff(b){
  ownedBuffs.add(b.id);
  activeBuffs.push(b);
  b.apply();
  sfxUpgrade();
  addFloat(W()/2, H()/2, `вњ¦ ${b.name}`, b.rarity==='legendary'?'#ffd700':b.rarity==='epic'?'#ff00ff':b.rarity==='rare'?'#00aaff':'#00ffcc');
  updateActiveBuffsUI();
  document.getElementById('buff-choices').style.display='none';
  if(casinoCoins>0){
    document.getElementById('spin-btn').disabled=false;
    document.getElementById('reel1').textContent='?';
    document.getElementById('reel2').textContent='?';
    document.getElementById('reel3').textContent='?';
  } else {
    closeCasino();
  }
}

function updateActiveBuffsUI(){
  const c=document.getElementById('active-buffs');
  c.innerHTML='';
  activeBuffs.forEach(b=>{
    const d=document.createElement('div');
    d.className='abuff';
    d.textContent=`${b.icon} ${b.name}`;
    c.appendChild(d);
  });
}

function updateAbilityUI(){
  abilities.forEach((ab,i)=>{
    const el=document.getElementById(`ability-${i}`);
    if(ab){
      el.style.display='flex';
      el.querySelector('.ab-icon').textContent=ab.icon;
    } else {
      el.style.display='none';
    }
  });
}

function useAbility(idx){
  const ab=abilities[idx];
  if(!ab||abilityCooldowns[idx]>0) return;
  ab.action();
  abilityCooldowns[idx]=ab.cooldown;
  sfx(400,.15,.06,'sine'); sfx(800,.1,.05);
}

function tickAbilities(){
  abilities.forEach((ab,i)=>{
    if(!ab) return;
    if(abilityCooldowns[i]>0) abilityCooldowns[i]--;
    const el=document.getElementById(`ability-${i}`);
    const ov=el.querySelector('.cd-overlay');
    if(abilityCooldowns[i]>0){
      const pct=abilityCooldowns[i]/ab.cooldown*100;
      ov.style.height=pct+'%';
      el.style.opacity='.5';
    } else {
      ov.style.height='0%';
      el.style.opacity='1';
    }
  });
  // Gold rush timer
  if(buffMods._goldRushTimer>0) buffMods._goldRushTimer--;
  // Overcharge timer
  if(buffMods._overchargeTimer>0) buffMods._overchargeTimer--;
  // Build ban
  if(buffMods.buildBanWaves!==undefined && buffMods.buildBanWaves>0 && buffMods._buildBanCheck){
    // (decremented in sendNextWave)
  }
}

// Farm income вЂ” called when wave clears
function collectFarmIncome(){
  let total=0;
  towers.forEach(t=>{
    const def=TDEFS[t.type];
    if(def.farm){
      let income=t.farm||def.farm;
      income=Math.round(income*buffMods.farmMul);
      total+=income;
      addFloat(t.x,t.y-10,`+${income}G`,'#ffd700');
      spawnP(t.x,t.y,3,'#ffd700',2,12,2);
    }
  });
  if(buffMods.doubleFarm){
    total*=2;
  }
  total+=buffMods.bonusGoldWave;
  if(total>0){
    gold+=total;
    addFloat(W()/2,H()/2+30,`INCOME: +${total}G`,'#ffd700');
  }
}

// Apply buff modifiers to damage
function getBuffedDmg(baseDmg){
  let d=baseDmg*buffMods.dmgMul;
  if(buffMods.critChance>0 && Math.random()<buffMods.critChance){
    d*=buffMods.critMul;
  }
  return d;
}

// =============================================================
//  WAVE GENERATION
// =============================================================
const TOTAL_WAVES = 30;

function genWaves() {
  const ws = [];
  for (let w = 1; w <= TOTAL_WAVES; w++) {
    const list = [];
    const hpS = 1 + w * 0.15;
    // Normal
    const n = 3 + Math.floor(w * 0.9);
    for (let i = 0; i < n; i++)
      list.push({ type:'normal', hp:Math.round((15+w*7)*hpS), speed:.00042+Math.min(w*.000015,.00035), reward:5+Math.floor(w/3) });
    // Fast w4+
    if (w >= 4) for (let i = 0; i < Math.floor(w*.4); i++)
      list.push({ type:'fast', hp:Math.round((10+w*4)*hpS), speed:.0007+Math.min(w*.00001,.00025), reward:6+Math.floor(w/3) });
    // Swarm w5+
    if (w >= 5) for (let i = 0; i < Math.floor(w*.5); i++)
      list.push({ type:'swarm', hp:Math.round((6+w*2)*hpS), speed:.00055, reward:2 });
    // Tank w6+
    if (w >= 6) for (let i = 0; i < Math.floor(w/4); i++)
      list.push({ type:'tank', hp:Math.round((60+w*16)*hpS), speed:.00028, reward:14+w });
    // Splitter w7+
    if (w >= 7) for (let i = 0; i < Math.floor(w/5); i++)
      list.push({ type:'splitter', hp:Math.round((30+w*8)*hpS), speed:.00036, reward:10+Math.floor(w/2) });
    // Shield w8+
    if (w >= 8) for (let i = 0; i < Math.floor(w/5); i++)
      list.push({ type:'shield', hp:Math.round((40+w*9)*hpS), speed:.00036, reward:12+w, shield:20+w*5 });
    // Armored w9+
    if (w >= 9) for (let i = 0; i < Math.floor(w/6); i++)
      list.push({ type:'armored', hp:Math.round((50+w*14)*hpS), speed:.00032, reward:16+w, armor:0.4 });
    // Healer w10+
    if (w >= 10) for (let i = 0; i < Math.max(1,Math.floor(w/8)); i++)
      list.push({ type:'healer', hp:Math.round((35+w*7)*hpS), speed:.00034, reward:15+w, healAmt:Math.round(2+w*.5) });
    // Regen w12+
    if (w >= 12) for (let i = 0; i < Math.floor(w/7); i++)
      list.push({ type:'regen', hp:Math.round((45+w*10)*hpS), speed:.00035, reward:14+w, regenAmt:Math.round(1+w*.3) });
    // Stealth w14+
    if (w >= 14) for (let i = 0; i < Math.floor(w/8); i++)
      list.push({ type:'stealth', hp:Math.round((25+w*6)*hpS), speed:.0005, reward:13+w });
    // Boss every 5
    if (w % 5 === 0)
      list.push({ type:'boss', hp:Math.round((200+w*50)*hpS), speed:.00018, reward:60+w*5 });
    // Shuffle
    for (let i = list.length-1; i > 0; i--) { const j=Math.floor(Math.random()*(i+1)); [list[i],list[j]]=[list[j],list[i]]; }
    ws.push(list);
  }
  return ws;
}

// =============================================================
//  GAME STATE
// =============================================================
let gold, lives, score, wave, waveActive, waveEnemies, spawnIdx, spawnTimer;
let towers, enemies, projectiles, particles, floatTexts;
let selectedDef, selectedTower, hoverCell;
let gameRunning = false;
let gt = 0;
const CELL = 40;
let waves;

function resetState() {
  gold=200; lives=25; score=0; wave=0;
  waveActive=false; waveEnemies=[]; spawnIdx=0; spawnTimer=0;
  towers=[]; enemies=[]; projectiles=[]; particles=[]; floatTexts=[];
  selectedDef=-1; selectedTower=null; hoverCell=null;
  researchPoints=0; unlockedTowers=new Set([0,3,6]); waveRPGiven=false;
  casinoCoins=0; ownedBuffs=new Set(); activeBuffs=[]; slotSpinning=false;
  abilities=[null,null]; abilityCooldowns=[0,0];
  buffMods={dmgMul:1,rateMul:1,rangeMul:1,splashMul:1,slowMul:1,dotMul:1,chainAdd:0,farmMul:1,goldPerKill:0,extraLives:0,bonusGoldWave:0,critChance:0,critMul:1.5,stunChance:0,pierce:false,lifesteal:0,aoeOnKill:0,towerDiscount:0,upgradeDiscount:0,enemySlow:0,startGold:0,speed4x:false,autoWave:false};
  autoWaveTimer=0; killCount=0;
  waves=genWaves();
  updateRPDisplay();
  updateCoinDisplay();
  updateActiveBuffsUI();
  updateAbilityUI();
}

// =============================================================
//  PLACEMENT
// =============================================================
function onPath(cx,cy) {
  const px=cx*CELL+CELL/2, py=cy*CELL+CELL/2;
  for (const p of PATH) if (Math.hypot(p.x-px,p.y-py) < CELL*1.1) return true;
  return false;
}
function hasTower(cx,cy) { return towers.some(t=>t.cx===cx&&t.cy===cy); }
function canPlace(cx,cy) {
  if (cx<0||cy<0||cx>=Math.ceil(W()/CELL)||cy>=Math.ceil((H()-80)/CELL)) return false;
  return !onPath(cx,cy) && !hasTower(cx,cy);
}

// =============================================================
//  PARTICLES / FLOAT TEXT
// =============================================================
function spawnP(x,y,n,color,spd=2,life=25,sz=2.5) {
  for (let i=0;i<n;i++){
    const a=Math.random()*TAU, s=Math.random()*spd+spd*.3;
    particles.push({x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s,life,maxLife:life,color,size:Math.random()*sz+1});
  }
}
function addFloat(x,y,text,color='#fff') {
  floatTexts.push({x,y,text,color,life:50,vy:-1.2});
}

// =============================================================
//  UPDATE  (called per tick at 60 fps logical)
// =============================================================
function tick() {
  gt++;

  // ---- Spawn ----
  if (waveActive && spawnIdx < waveEnemies.length) {
    spawnTimer--;
    if (spawnTimer <= 0) {
      const d = waveEnemies[spawnIdx];
      enemies.push({...d, x:PATH[0].x, y:PATH[0].y, progress:0, maxHp:d.hp,
        maxShield:d.shield||0, slow:0, slowTimer:0, dead:false, prevX:PATH[0].x, prevY:PATH[0].y,
        dotDmg:0, dotTimer:0, stunTimer:0, visible:true, stealthTimer:0,
        armor:d.armor||0, regenAmt:d.regenAmt||0, healAmt:d.healAmt||0, isMini:false });
      spawnIdx++;
      spawnTimer = d.type==='boss'?130:50;
    }
  }

  // Next wave btn
  const idle = enemies.length===0 && (!waveActive || spawnIdx>=waveEnemies.length);
  document.getElementById('next-wave-btn').style.display = (idle && wave < TOTAL_WAVES) ? 'block' : 'none';

  // Award RP when wave clears
  if (idle && waveActive && wave > 0 && !waveRPGiven) {
    waveActive = false; waveRPGiven = true;
    researchPoints++;
    updateRPDisplay();
    addFloat(W()/2, H()/2 - 30, '+1 RESEARCH POINT', '#ffcc00');
    collectFarmIncome();
  }

  // Tick abilities & buff timers
  tickAbilities();

  // Auto-wave buff
  if(buffMods.autoWave && idle && wave<TOTAL_WAVES && wave>0){
    autoWaveTimer=(autoWaveTimer||0)+1;
    if(autoWaveTimer>=300){autoWaveTimer=0;sendNextWave();}
  } else { autoWaveTimer=0; }

  // Check win
  if (idle && wave >= TOTAL_WAVES && lives > 0) {
    gameRunning = false;
    document.getElementById('win-screen').style.display = 'flex';
    document.getElementById('win-score').textContent = `SCORE: ${score.toLocaleString()}`;
    return;
  }

  // ---- Move enemies ----
  enemies.forEach(e => {
    if (e.dead) return;
    e.prevX = e.x; e.prevY = e.y;
    const spd = (e.stunTimer > 0 ? 0 : e.speed) * (1 - e.slow * 0.55);
    e.progress += spd;
    const pos = pathPos(clamp(e.progress,0,1));
    e.x = pos.x; e.y = pos.y;
    if (e.slowTimer > 0) e.slowTimer--; else e.slow = 0;
    if (e.progress >= 1) {
      e.dead = true; lives--; sfxLeak();
      addFloat(e.x,e.y,'-1 в™Ґ','#ff3366');
      if (lives <= 0) gameOver();
    }
  });
  enemies = enemies.filter(e=>!e.dead);

  // ---- Enemy abilities ----
  enemies.forEach(e => {
    if (e.dead) return;
    // Stun countdown
    if (e.stunTimer > 0) e.stunTimer--;
    // DoT
    if (e.dotDmg > 0) { e.hp -= e.dotDmg; e.dotTimer--; if (e.dotTimer<=0) e.dotDmg=0; }
    // Regen
    if (e.regenAmt > 0 && gt%30===0) e.hp = Math.min(e.maxHp, e.hp + e.regenAmt);
    // Healer
    if (e.type==='healer' && gt%60===0) {
      enemies.forEach(e2 => {
        if (e2!==e && !e2.dead && dst(e,e2)<80) e2.hp = Math.min(e2.maxHp, e2.hp + e.healAmt);
      });
    }
    // Stealth
    if (e.type==='stealth') {
      if(buffMods.revealStealth) { e.visible=true; }
      else { e.stealthTimer=(e.stealthTimer||0)+1; e.visible=e.stealthTimer%180<120; }
    }
    // Magnetic field buff вЂ” slow near towers
    if(buffMods.magneticField){
      let nearTower=towers.some(t=>dst(t,e)<100);
      if(nearTower&&!e.dead){e.slow=Math.max(e.slow,.15);e.slowTimer=Math.max(e.slowTimer,5);}
    }
    // Enemy slow buff
    if(buffMods.enemySlow>0){e.slow=Math.max(e.slow,buffMods.enemySlow);e.slowTimer=Math.max(e.slowTimer,5);}
  });

  // ---- Tower synergy buff ----
  if(buffMods.synergy){
    towers.forEach(t=>{
      t._synergyBonus=towers.some(t2=>t2!==t&&dst(t,t2)<80)?1.2:1;
    });
  }

  // ---- Towers attack ----
  towers.forEach(t => {
    const def = TDEFS[t.type];
    if(def.farm) return; // farm towers don't attack
    t.cooldown = Math.max(0, t.cooldown - 1);

    // Find target (furthest along path in range)
    let tgt = null, best = -1;
    enemies.forEach(e => {
      if (e.dead) return;
      if (e.type==='stealth' && !e.visible) return;
      const d = dst(t,e);
      if (d <= t.range && e.progress > best) { best = e.progress; tgt = e; }
    });
    t.target = tgt;

    if (!tgt) {
      t.beamAlpha = Math.max(0, (t.beamAlpha||0) - 0.06);
      return;
    }
    t.angle = Math.atan2(tgt.y - t.y, tgt.x - t.x);

    // Frenzy buff вЂ” fire faster when few enemies
    const frenzyMul = (buffMods.frenzy && enemies.length<3) ? .5 : 1;
    // Overcharge buff
    const overchargeDmgMul = buffMods.overcharge && buffMods._overchargeTimer>0 ? 2 : 1;
    const overchargeRateMul = buffMods.overcharge && buffMods._overchargeTimer>0 ? 1.3 : 1;
    const synergyMul = t._synergyBonus||1;

    if (def.beam) {
      t.beamAlpha = Math.min(1, (t.beamAlpha||0) + 0.1);
      applyDmg(tgt, t.dmg*overchargeDmgMul*synergyMul, t);
      if (gt%5===0) spawnP(tgt.x,tgt.y,1,def.color,1.5,10,1.5);
    } else if (t.cooldown <= 0) {
      t.cooldown = Math.round(t.rate * buffMods.rateMul * frenzyMul * overchargeRateMul);
      sfxShoot();
      // Predictive aiming вЂ” lead the target
      const pSpeed = 12;
      const d2t = dst(t, tgt);
      const tFrames = d2t / pSpeed;
      const evx = tgt.x - (tgt.prevX || tgt.x);
      const evy = tgt.y - (tgt.prevY || tgt.y);
      const predX = tgt.x + evx * tFrames * 0.8;
      const predY = tgt.y + evy * tFrames * 0.8;
      const a = Math.atan2(predY - t.y, predX - t.x);
      const projDmg = t.dmg * overchargeDmgMul * synergyMul;
      const projChain = (t.chain||def.chain||0) + buffMods.chainAdd;
      const projDot = (t.dot||def.dot||0) * buffMods.dotMul;
      const projSlow = (t.slow||0) * buffMods.slowMul;
      const projSplash = (t.splash||0) * buffMods.splashMul;
      projectiles.push({
        x:t.x, y:t.y, vx:Math.cos(a)*pSpeed, vy:Math.sin(a)*pSpeed,
        dmg:projDmg, color:def.color, splash:projSplash,
        slow:projSlow, pierce:def.pierce||buffMods.pierce,
        dot:projDot, chain:projChain,
        homing:def.homing||false, stun:t.stun||def.stun||0, shieldBreak:def.shieldBreak||false,
        life:80, size:def.splash?4:3, trail:[],
      });
      // Multishot buff for Gatling
      if(buffMods.multishot && t.type===1){
        const a2=a+(Math.random()-.5)*.15;
        projectiles.push({
          x:t.x, y:t.y, vx:Math.cos(a2)*pSpeed, vy:Math.sin(a2)*pSpeed,
          dmg:projDmg*.7, color:def.color, splash:0,
          slow:projSlow, pierce:false, dot:projDot, chain:0,
          homing:false, stun:0, shieldBreak:false,
          life:80, size:2, trail:[],
        });
      }
    }
  });

  // ---- Projectiles ----
  projectiles.forEach(p => {
    // Homing
    if (p.homing) {
      let nearest=null, nd=Infinity;
      enemies.forEach(e=>{if(!e.dead){const d=dst(p,e);if(d<nd){nd=d;nearest=e;}}});
      if (nearest) {
        const wa=Math.atan2(nearest.y-p.y,nearest.x-p.x);
        const ca=Math.atan2(p.vy,p.vx);
        let da=wa-ca; while(da>PI)da-=TAU; while(da<-PI)da+=TAU;
        const na=ca+clamp(da,-.08,.08);
        const sp=Math.hypot(p.vx,p.vy);
        p.vx=Math.cos(na)*sp; p.vy=Math.sin(na)*sp;
      }
    }
    p.x+=p.vx; p.y+=p.vy; p.life--;
    p.trail.push({x:p.x,y:p.y,life:6});
    p.trail = p.trail.filter(t=>{t.life--;return t.life>0;});

    for (const e of enemies) {
      if (e.dead) continue;
      if (dst(p,e)<20) {
        applyDmg(e, p.dmg, p);
        if (p.splash>0) {
          sfxBoom();
          spawnP(p.x,p.y,10,p.color,4,22,3);
          enemies.forEach(e2=>{
            if(e2!==e&&!e2.dead&&dst(p,e2)<p.splash) applyDmg(e2,p.dmg*.4,p);
          });
        } else { spawnP(p.x,p.y,3,p.color,2,10,2); }
        // Chain lightning
        if (p.chain > 0) {
          let targets = enemies.filter(e2=>e2!==e&&!e2.dead&&dst(e,e2)<100).sort((a,b)=>dst(e,a)-dst(e,b));
          let cd = p.dmg * 0.6;
          for (let ci=0; ci<Math.min(p.chain,targets.length); ci++) {
            applyDmg(targets[ci], cd, {slow:0});
            spawnP(targets[ci].x,targets[ci].y,2,p.color,2,8,1.5);
            cd *= 0.7;
          }
        }
        if (!p.pierce) p.life=0;
        break;
      }
    }
  });
  projectiles = projectiles.filter(p=>p.life>0);

  // ---- Cleanup dead ----
  enemies = enemies.filter(e=>{
    if(e.hp<=0){
      let rw = e.reward + buffMods.goldPerKill;
      if(buffMods._goldRushTimer>0) rw*=2;
      gold+=rw; score+=e.reward*10;
      killCount=(killCount||0)+1;
      // Lifesteal buff
      if(buffMods.lifesteal>0 && killCount%50===0){ lives++; addFloat(e.x,e.y,'+1 в™Ґ','#ff88ff'); }
      sfxKill();
      spawnP(e.x,e.y,8,'#ff00ff',3,18,3);
      addFloat(e.x,e.y,`+${rw}G`,'#ffcc00');
      // AoE on kill buff
      if(buffMods.aoeOnKill>0){
        const aoeDmg=e.maxHp*buffMods.aoeOnKill;
        enemies.forEach(e2=>{if(e2!==e&&!e2.dead&&dst(e,e2)<60){e2.hp-=aoeDmg;}});
        spawnP(e.x,e.y,6,'#ff6600',3,14,2);
      }
      // Overkill buff
      if(buffMods.overkill){
        const excess=Math.abs(e.hp);
        if(excess>0){
          let nearest=null,nd=Infinity;
          enemies.forEach(e2=>{if(e2!==e&&!e2.dead){const d=dst(e,e2);if(d<nd){nd=d;nearest=e2;}}});
          if(nearest&&nd<120) nearest.hp-=excess;
        }
      }
      // Cryo cascade buff
      if(buffMods.cryoCascade && e.slow>.3){
        enemies.forEach(e2=>{if(e2!==e&&!e2.dead&&dst(e,e2)<70){e2.slow=Math.max(e2.slow,.5);e2.slowTimer=60;}});
        spawnP(e.x,e.y,5,'#00aaff',3,15,2);
      }
      // Poison cloud buff
      if(buffMods.poisonCloud && e.dotDmg>0){
        enemies.forEach(e2=>{if(e2!==e&&!e2.dead&&dst(e,e2)<60){e2.dotDmg=Math.max(e2.dotDmg,1.5);e2.dotTimer=Math.max(e2.dotTimer,300);}});
        spawnP(e.x,e.y,4,'#44ff00',2,15,2);
      }
      // Splitter: spawn mini enemies (unless banned)
      if (e.type==='splitter' && !e.isMini && !buffMods.noSplit) {
        for (let si=0;si<2;si++) {
          enemies.push({
            type:'swarm', hp:Math.round(e.maxHp*.25), maxHp:Math.round(e.maxHp*.25),
            speed:e.speed*1.3, reward:Math.floor(e.reward*.3),
            x:e.x+(si?8:-8), y:e.y, prevX:e.x, prevY:e.y,
            progress:e.progress, dead:false, slow:0, slowTimer:0,
            maxShield:0, shield:0, isMini:true,
            dotDmg:0, dotTimer:0, stunTimer:0, visible:true, stealthTimer:0,
            armor:0, regenAmt:0, healAmt:0
          });
        }
      }
      // Ricochet buff
      if(buffMods.ricochet && !e._ricocheted){
        let nearest=null,nd=Infinity;
        enemies.forEach(e2=>{if(e2!==e&&!e2.dead){const d=dst(e,e2);if(d<nd&&d<100){nd=d;nearest=e2;}}});
        if(nearest){applyDmg(nearest,e.reward*2,{slow:0});spawnP(nearest.x,nearest.y,2,'#ff88ff',2,8,1.5);}
      }
      return false;
    }
    return true;
  });

  // ---- Particles ----
  particles.forEach(p=>{p.x+=p.vx;p.y+=p.vy;p.vx*=.94;p.vy*=.94;p.life--;});
  particles=particles.filter(p=>p.life>0);

  // ---- Float text ----
  floatTexts.forEach(f=>{f.y+=f.vy;f.life--;});
  floatTexts=floatTexts.filter(f=>f.life>0);

  updateHUD();
}

function applyDmg(e, dmg, src) {
  // Buff: crit chance
  dmg = getBuffedDmg(dmg);
  // Armor pierce buff
  let armorVal = e.armor||0;
  if(buffMods.armorPierce) armorVal *= (1 - buffMods.armorPierce);
  if (armorVal) dmg *= (1 - armorVal);
  // Shield break
  if (src && src.shieldBreak && e.shield > 0) {
    const breakMul = buffMods.shieldBreakMul||1;
    e.shield = Math.max(0, e.shield - e.maxShield*0.5*breakMul);
    if(breakMul>1) e.shield=0;
  } else if (e.shield > 0) {
    const abs = Math.min(e.shield, dmg*.6);
    e.shield -= abs; e.hp -= (dmg-abs);
  } else e.hp -= dmg;
  if (src && src.slow > 0) { e.slow = Math.max(e.slow, src.slow); e.slowTimer = 35; }
  if (src && src.dot > 0) { e.dotDmg = Math.max(e.dotDmg, src.dot/60); e.dotTimer = Math.max(e.dotTimer, 180); }
  if (src && src.stun > 0) { e.stunTimer = Math.max(e.stunTimer||0, src.stun); }
  // Stun chance buff
  if(buffMods.stunChance>0 && Math.random()<buffMods.stunChance){ e.stunTimer=Math.max(e.stunTimer||0,60); }
}

// =============================================================
//  RENDERING  (requestAnimationFrame with lerp for smoothness)
// =============================================================
function render(alpha) {
  const w = W(), h = H();
  const bg = X.createLinearGradient(0,0,0,h);
  bg.addColorStop(0,'#04000a');
  bg.addColorStop(.3,'#0a0018');
  bg.addColorStop(.45,'#150028');
  bg.addColorStop(.5,'#0c0018');
  bg.addColorStop(1,'#0a0014');
  X.fillStyle = bg;
  X.fillRect(0,0,w,h);

  drawBackground();
  drawGrid();
  drawPath();
  drawGhostPreview();
  drawRangeCircle();
  drawTowers();
  drawEnemies(alpha);
  drawProjectiles(alpha);
  drawParticles(alpha);
  drawFloatTexts(alpha);
  drawVignette();
  drawScanlines();
}

// =============================================================
//  BACKGROUND SCENERY
// =============================================================
function drawBackground() {
  const w = W(), h = H();
  const horizY = h * 0.44;

  // === STARS ===
  for (let i = 0; i < 90; i++) {
    const sx = (i * 137.508 + 23) % w;
    const sy = (i * 97.531 + 11) % (h * 0.42);
    const twinkle = 0.2 + 0.8 * Math.abs(Math.sin(gt * 0.012 + i * 1.7));
    X.globalAlpha = twinkle * 0.5;
    X.fillStyle = i % 7 === 0 ? '#ff88ff' : i % 11 === 0 ? '#88ffff' : '#ffffff';
    X.beginPath(); X.arc(sx, sy, 0.5 + (i % 4) * 0.4, 0, TAU); X.fill();
  }
  X.globalAlpha = 1;

  // === SYNTHWAVE SUN ===
  const sunX = w * 0.5, sunYp = h * 0.33, sunR = Math.min(90, w * 0.065);
  const sg = X.createRadialGradient(sunX, sunYp, 0, sunX, sunYp, sunR);
  sg.addColorStop(0, '#ffcc44');
  sg.addColorStop(0.25, '#ff8800');
  sg.addColorStop(0.5, '#ff0066');
  sg.addColorStop(0.8, 'rgba(204,0,255,.25)');
  sg.addColorStop(1, 'rgba(204,0,255,0)');
  X.fillStyle = sg;
  X.beginPath(); X.arc(sunX, sunYp, sunR, 0, TAU); X.fill();

  // Sun horizontal stripe mask
  X.fillStyle = '#04000a';
  for (let i = 0; i < 10; i++) {
    const sy2 = sunYp + sunR * 0.05 + i * (sunR * 0.95 / 10);
    const gap = 1.2 + i * 1.6;
    const dy = sy2 - sunYp;
    const halfW = Math.sqrt(Math.max(0, sunR * sunR - dy * dy));
    if (halfW > 0) X.fillRect(sunX - halfW, sy2, halfW * 2, gap);
  }

  // Sun upper glow
  X.save();
  X.shadowColor = '#ff0066'; X.shadowBlur = 50;
  X.strokeStyle = 'rgba(255,0,102,.05)'; X.lineWidth = 4;
  X.beginPath(); X.arc(sunX, sunYp, sunR + 10, PI, TAU); X.stroke();
  X.shadowBlur = 0; X.restore();

  // === MOUNTAINS ===
  X.fillStyle = 'rgba(8,0,18,.85)';
  X.beginPath(); X.moveTo(0, horizY);
  for (let i = 0; i <= 22; i++) {
    const mx = (i / 22) * w;
    const mh = 18 + Math.sin(i * 1.3 + 5) * 32 + Math.cos(i * 2.7) * 22;
    X.lineTo(mx, horizY - mh);
  }
  X.lineTo(w, horizY); X.lineTo(w, h); X.lineTo(0, h); X.closePath(); X.fill();

  // Mountain edge glow
  X.strokeStyle = 'rgba(255,0,255,.1)'; X.lineWidth = 1;
  X.beginPath(); X.moveTo(0, horizY);
  for (let i = 0; i <= 22; i++) {
    const mx = (i / 22) * w;
    const mh = 18 + Math.sin(i * 1.3 + 5) * 32 + Math.cos(i * 2.7) * 22;
    X.lineTo(mx, horizY - mh);
  }
  X.stroke();

  // === CITY BUILDINGS ===
  _drawBldgs(w * 0.02, w * 0.18, horizY);
  _drawBldgs(w * 0.82, w * 0.98, horizY);
  _drawBldgs(w * 0.42, w * 0.58, horizY);

  // === HORIZON GLOW LINE ===
  const hg = X.createLinearGradient(0, horizY - 8, 0, horizY + 18);
  hg.addColorStop(0, 'rgba(255,0,255,0)');
  hg.addColorStop(0.4, 'rgba(255,0,102,.14)');
  hg.addColorStop(0.6, 'rgba(255,0,255,.08)');
  hg.addColorStop(1, 'rgba(255,0,255,0)');
  X.fillStyle = hg; X.fillRect(0, horizY - 8, w, 26);

  // === PERSPECTIVE GRID (ground) ===
  X.strokeStyle = 'rgba(255,0,255,.05)'; X.lineWidth = 0.5;
  for (let i = 0; i < 18; i++) {
    const t = i / 18;
    const yy = horizY + t * t * (h - horizY);
    X.globalAlpha = 0.14 * (1 - t * 0.7);
    X.beginPath(); X.moveTo(0, yy); X.lineTo(w, yy); X.stroke();
  }
  const vpx = w / 2;
  X.strokeStyle = 'rgba(255,0,255,.03)';
  for (let i = -10; i <= 10; i++) {
    X.globalAlpha = 0.1 * (1 - Math.abs(i) / 12);
    X.beginPath(); X.moveTo(vpx + i * 8, horizY); X.lineTo(vpx + i * (w / 10), h); X.stroke();
  }
  X.globalAlpha = 1;

  // === FLOATING NEON DIAMONDS ===
  for (let i = 0; i < 5; i++) {
    const fx = (i * 311.7 + 100) % (w * 0.8) + w * 0.1;
    const fy = (i * 197.3 + 200) % (h * 0.3) + h * 0.5;
    const pulse = 0.025 + Math.sin(gt * 0.014 + i * 3) * 0.012;
    X.save(); X.translate(fx, fy); X.rotate(gt * 0.002 + i);
    X.strokeStyle = `rgba(0,255,255,${pulse})`; X.lineWidth = 0.5;
    const dr = 5 + i * 2;
    X.beginPath(); X.moveTo(0,-dr); X.lineTo(dr,0); X.lineTo(0,dr); X.lineTo(-dr,0); X.closePath(); X.stroke();
    X.restore();
  }
}

function _drawBldgs(x1, x2, horizY) {
  const range = x2 - x1;
  const count = Math.floor(range / 16);
  for (let i = 0; i < count; i++) {
    const bx = x1 + (i / count) * range;
    const bw = 7 + Math.sin(bx * 0.1) * 5;
    const bh = 18 + Math.abs(Math.sin(bx * 0.07 + 3)) * 55;
    const by = horizY - bh;
    X.fillStyle = '#050010'; X.fillRect(bx, by, bw, bh);
    X.strokeStyle = 'rgba(255,0,255,.06)'; X.lineWidth = 0.5; X.strokeRect(bx, by, bw, bh);
    // Window lights
    for (let wy = by + 3; wy < by + bh - 2; wy += 5) {
      for (let wx = bx + 2; wx < bx + bw - 2; wx += 4) {
        if (Math.sin(wx * 17.3 + wy * 7.1) > 0.35) {
          X.fillStyle = Math.sin(wx * 3 + wy) > 0 ? 'rgba(255,0,255,.1)' : 'rgba(0,255,255,.08)';
          X.fillRect(wx, wy, 1.5, 1.5);
        }
      }
    }
    // Antenna + blinking light
    if (i % 3 === 0) {
      X.strokeStyle = 'rgba(255,0,255,.12)'; X.lineWidth = 0.5;
      X.beginPath(); X.moveTo(bx + bw / 2, by); X.lineTo(bx + bw / 2, by - 8); X.stroke();
      if (Math.sin(gt * 0.07 + i * 2) > 0.5) {
        X.fillStyle = '#ff0066';
        X.beginPath(); X.arc(bx + bw / 2, by - 8, 1, 0, TAU); X.fill();
      }
    }
  }
}

function drawGrid() {
  X.strokeStyle = 'rgba(255,0,255,.035)';
  X.lineWidth = .5;
  for (let x = 0; x < W(); x += CELL) { X.beginPath(); X.moveTo(x,0); X.lineTo(x,H()); X.stroke(); }
  for (let y = 0; y < H(); y += CELL) { X.beginPath(); X.moveTo(0,y); X.lineTo(W(),y); X.stroke(); }
}

function drawPath() {
  if (PATH.length < 2) return;

  // Outer glow
  X.save();
  X.shadowColor='#ff00ff'; X.shadowBlur=30;
  X.strokeStyle='rgba(255,0,255,.12)';
  X.lineWidth=44; X.lineCap='round'; X.lineJoin='round';
  X.beginPath(); X.moveTo(PATH[0].x,PATH[0].y);
  for (let i=1;i<PATH.length;i++) X.lineTo(PATH[i].x,PATH[i].y);
  X.stroke(); X.shadowBlur=0; X.restore();

  // Surface
  X.strokeStyle='rgba(25,0,45,.92)';
  X.lineWidth=34; X.lineCap='round'; X.lineJoin='round';
  X.beginPath(); X.moveTo(PATH[0].x,PATH[0].y);
  for (let i=1;i<PATH.length;i++) X.lineTo(PATH[i].x,PATH[i].y);
  X.stroke();

  // Borders
  X.strokeStyle='rgba(255,0,255,.3)';
  X.lineWidth=1.2; X.setLineDash([7,7]);
  for (const side of [-1,1]) {
    X.beginPath();
    for (let i=0;i<PATH.length-1;i++) {
      const dx=PATH[i+1].x-PATH[i].x, dy=PATH[i+1].y-PATH[i].y;
      const l=Math.hypot(dx,dy)||1;
      const nx=-dy/l*17*side, ny=dx/l*17*side;
      i===0 ? X.moveTo(PATH[i].x+nx,PATH[i].y+ny) : X.lineTo(PATH[i].x+nx,PATH[i].y+ny);
    }
    X.stroke();
  }
  X.setLineDash([]);

  // Flow dots
  const off = (gt * .003) % 1;
  for (let i=0;i<25;i++) {
    const prog = ((i/25)+off)%1;
    const pos = pathPos(prog);
    const a = .25+.25*Math.sin(gt*.06+i);
    X.fillStyle=`rgba(255,0,255,${a})`;
    X.beginPath(); X.arc(pos.x,pos.y,1.8,0,TAU); X.fill();
  }
}

function drawTowers() {
  towers.forEach(t => {
    const def = TDEFS[t.type];
    const px=t.x, py=t.y;
    const lvl = t.level;
    const glowR = 30 + lvl * 6;
    const baseR = 17 + lvl * 1.5;
    const sides = 6 + lvl; // more sides = smoother at higher level

    // Ground glow вЂ” grows with level
    const glow = X.createRadialGradient(px,py,0,px,py,glowR);
    glow.addColorStop(0, def.color + (lvl>=2?'38':'22'));
    glow.addColorStop(.6, def.color + '10');
    glow.addColorStop(1, def.color + '00');
    X.fillStyle=glow;
    X.beginPath(); X.arc(px,py,glowR,0,TAU); X.fill();

    // Pulsing ring at lvl 2+
    if (lvl >= 2) {
      const rr = baseR + 6 + Math.sin(gt*.04)*3;
      X.strokeStyle = def.color + '18';
      X.lineWidth = 1;
      X.beginPath(); X.arc(px,py,rr,0,TAU); X.stroke();
    }

    X.save(); X.translate(px,py);

    // === BASE PLATFORM ===
    // Outer ring at lvl 1+
    if (lvl >= 1) {
      X.strokeStyle = def.color + '30';
      X.lineWidth = 1;
      X.beginPath();
      for (let i=0;i<sides+2;i++){const a=(i/(sides+2))*TAU; X.lineTo(Math.cos(a)*(baseR+4),Math.sin(a)*(baseR+4));}
      X.closePath(); X.stroke();
    }

    // Main base polygon
    X.strokeStyle = def.color + (lvl>=2?'cc':'80');
    X.lineWidth = 1.5 + lvl * 0.3;
    X.fillStyle = `rgba(${lvl>=3?'20,5,50':'12,0,25'},.85)`;
    X.beginPath();
    for (let i=0;i<sides;i++){ const a=(i/sides)*TAU-PI/6; X.lineTo(Math.cos(a)*baseR,Math.sin(a)*baseR); }
    X.closePath(); X.fill(); X.stroke();

    // Inner decorative geometry
    if (lvl >= 1) {
      X.strokeStyle = def.color + '25';
      X.lineWidth = .8;
      X.beginPath();
      const innerR = baseR * .55;
      for (let i=0;i<sides;i++){ const a=(i/sides)*TAU-PI/6+PI/sides; X.lineTo(Math.cos(a)*innerR,Math.sin(a)*innerR); }
      X.closePath(); X.stroke();
      // Connect inner to outer
      for (let i=0;i<sides;i++){
        const a=(i/sides)*TAU-PI/6;
        X.beginPath();
        X.moveTo(Math.cos(a)*innerR*.6,Math.sin(a)*innerR*.6);
        X.lineTo(Math.cos(a)*baseR*.85,Math.sin(a)*baseR*.85);
        X.stroke();
      }
    }

    // Corner accent dots at lvl 2+
    if (lvl >= 2) {
      for (let i=0;i<sides;i++){
        const a=(i/sides)*TAU-PI/6;
        X.fillStyle = def.color + '60';
        X.beginPath(); X.arc(Math.cos(a)*baseR,Math.sin(a)*baseR, 1.5, 0, TAU); X.fill();
      }
    }

    // === TURRET (rotates) ===
    const ang = t.angle||0;
    X.rotate(ang);
    X.shadowColor=def.color;
    X.shadowBlur = 12 + lvl * 4;

    switch(t.type) {
      case 0: // BLASTER
        X.strokeStyle=def.color; X.lineWidth=2.5+lvl*.5;
        X.beginPath(); X.moveTo(6,0); X.lineTo(20+lvl*3,0); X.stroke();
        X.fillStyle=def.color+'30';
        X.fillRect(4,-3-lvl,10+lvl*2,6+lvl*2); X.strokeRect(4,-3-lvl,10+lvl*2,6+lvl*2);
        if(lvl>=1){X.strokeStyle=def.color+'50';X.lineWidth=1;X.beginPath();X.arc(20+lvl*3,0,2+lvl,0,TAU);X.stroke();}
        if(lvl>=3){X.strokeStyle=def.color;X.lineWidth=2;X.beginPath();X.moveTo(8,-4);X.lineTo(22,-3);X.stroke();X.beginPath();X.moveTo(8,4);X.lineTo(22,3);X.stroke();}
        break;

      case 1: // GATLING
        X.strokeStyle=def.color; X.lineWidth=2;
        for(let b=0;b<3;b++){
          const ba=b*TAU/3+gt*.05;
          X.beginPath();X.moveTo(Math.cos(ba)*3,Math.sin(ba)*3);X.lineTo(Math.cos(ba)*3+18+lvl*2,Math.sin(ba)*3);X.stroke();
        }
        X.strokeStyle=def.color+'60';X.lineWidth=1;
        X.beginPath();X.arc(8,0,5+lvl,0,TAU);X.stroke();
        if(lvl>=2){X.beginPath();X.arc(14+lvl,0,3+lvl,0,TAU);X.stroke();}
        break;

      case 2: // SNIPER
        X.strokeStyle=def.color; X.lineWidth=2;
        X.beginPath();X.moveTo(4,0);X.lineTo(28+lvl*4,0);X.stroke();
        X.strokeStyle=def.color+'40';X.lineWidth=1;
        X.beginPath();X.moveTo(4,-2);X.lineTo(28+lvl*4,-1);X.stroke();
        X.beginPath();X.moveTo(4,2);X.lineTo(28+lvl*4,1);X.stroke();
        X.fillStyle=def.color;X.beginPath();X.arc(12,0,2+lvl*.5,0,TAU);X.fill();
        if(lvl>=2){X.strokeStyle=def.color+'60';X.lineWidth=.8;X.beginPath();X.moveTo(10,-6);X.lineTo(14,-6);X.lineTo(14,-3);X.stroke();}
        break;

      case 3: // CANNON
        X.strokeStyle=def.color; X.lineWidth=2;
        X.fillStyle=def.color+'20';
        X.beginPath();X.moveTo(3,-5-lvl);X.lineTo(16+lvl*2,-4-lvl);X.lineTo(18+lvl*3,-1);X.lineTo(18+lvl*3,1);X.lineTo(16+lvl*2,4+lvl);X.lineTo(3,5+lvl);X.closePath();X.fill();X.stroke();
        X.lineWidth=2.5+lvl*.5;
        X.beginPath();X.moveTo(10,-3-lvl*.5);X.lineTo(20+lvl*3,-2-lvl*.3);X.stroke();
        X.beginPath();X.moveTo(10,3+lvl*.5);X.lineTo(20+lvl*3,2+lvl*.3);X.stroke();
        if(lvl>=2){const mx=20+lvl*3;X.lineWidth=1.5;X.beginPath();X.moveTo(mx-3,-5-lvl);X.lineTo(mx-3,5+lvl);X.stroke();X.beginPath();X.moveTo(mx,-6-lvl);X.lineTo(mx,6+lvl);X.stroke();}
        break;

      case 4: // MORTAR
        X.strokeStyle=def.color;X.lineWidth=2;
        X.fillStyle=def.color+'25';
        const mr=8+lvl*2;
        X.beginPath();X.arc(6,0,mr,-.5,.5);X.lineTo(6,-mr);X.closePath();X.fill();X.stroke();
        X.lineWidth=3+lvl;
        X.beginPath();X.moveTo(6,0);X.lineTo(14+lvl*2,-6-lvl);X.stroke();
        if(lvl>=1){X.fillStyle=def.color;X.beginPath();X.arc(14+lvl*2,-6-lvl,2+lvl*.5,0,TAU);X.fill();}
        if(lvl>=2){X.strokeStyle=def.color+'40';X.lineWidth=1;X.beginPath();X.arc(6,0,mr+3,0,TAU);X.stroke();}
        break;

      case 5: // ROCKET
        X.strokeStyle=def.color;X.lineWidth=1.5;X.fillStyle=def.color+'20';
        for(let r=0;r<2+lvl;r++){
          const ry=(r-(1+lvl)*.5+.5)*5;
          X.fillRect(4,ry-2,14+lvl*2,4);X.strokeRect(4,ry-2,14+lvl*2,4);
          X.fillStyle=def.color;X.beginPath();X.arc(18+lvl*2,ry,1.5,0,TAU);X.fill();X.fillStyle=def.color+'20';
        }
        if(lvl>=2){X.strokeStyle=def.color+'50';X.lineWidth=1;X.beginPath();X.moveTo(2,-8-lvl);X.lineTo(2,8+lvl);X.stroke();}
        break;

      case 6: { // CRYO
        X.strokeStyle=def.color;X.lineWidth=2;
        X.beginPath();X.moveTo(6,0);X.lineTo(18+lvl*2,0);X.stroke();
        const cr=4+lvl*1.5,ccx=18+lvl*2;
        X.fillStyle=def.color+'40';X.strokeStyle=def.color;X.lineWidth=1.5;
        X.beginPath();for(let i=0;i<6;i++){const a=(i/6)*TAU;const ir=i%2===0?cr:cr*.5;X.lineTo(ccx+Math.cos(a)*ir,Math.sin(a)*ir);}X.closePath();X.fill();X.stroke();
        if(lvl>=1){for(let i=0;i<3+lvl;i++){const a=gt*.03+i*TAU/(3+lvl);const fr=cr+3+Math.sin(gt*.06+i)*2;X.fillStyle=def.color+'40';X.beginPath();X.arc(ccx+Math.cos(a)*fr,Math.sin(a)*fr,1,0,TAU);X.fill();}}
        if(lvl>=2){X.strokeStyle=def.color+'50';X.lineWidth=1;for(let i=0;i<3;i++){const fx=8+i*3;X.beginPath();X.moveTo(fx,-5);X.lineTo(fx,5);X.stroke();}}
        break;
      }

      case 7: // FROSTBITE
        X.strokeStyle=def.color;X.lineWidth=1.5;
        for(let i=0;i<4+lvl;i++){
          const a=(i/(4+lvl))*TAU;const len=12+lvl*2;
          X.beginPath();X.moveTo(4*Math.cos(a),4*Math.sin(a));X.lineTo(Math.cos(a)*len,Math.sin(a)*len);X.stroke();
          if(lvl>=1){X.beginPath();X.moveTo(Math.cos(a)*len*.6+Math.cos(a+.5)*4,Math.sin(a)*len*.6+Math.sin(a+.5)*4);X.lineTo(Math.cos(a)*len*.6,Math.sin(a)*len*.6);X.stroke();}
        }
        X.fillStyle=def.color+'50';X.beginPath();X.arc(0,0,4+lvl,0,TAU);X.fill();
        break;

      case 8: // BLIZZARD
        X.strokeStyle=def.color;X.lineWidth=1;X.fillStyle=def.color+'30';
        for(let i=0;i<6;i++){
          const a=(i/6)*TAU+gt*.01;const d2=10+lvl*2;
          X.beginPath();X.moveTo(Math.cos(a)*d2-2,Math.sin(a)*d2);X.lineTo(Math.cos(a)*d2,Math.sin(a)*d2-3);X.lineTo(Math.cos(a)*d2+2,Math.sin(a)*d2);X.lineTo(Math.cos(a)*d2,Math.sin(a)*d2+3);X.closePath();X.fill();X.stroke();
        }
        X.strokeStyle=def.color+'40';X.beginPath();X.arc(0,0,10+lvl*2,0,TAU);X.stroke();
        if(lvl>=2){X.strokeStyle=def.color+'25';X.beginPath();X.arc(0,0,14+lvl*2,0,TAU);X.stroke();}
        X.lineWidth=2;X.strokeStyle=def.color;X.beginPath();X.moveTo(5,0);X.lineTo(8+lvl,0);X.stroke();
        break;

      case 9: { // LASER
        X.strokeStyle=def.color;X.lineWidth=2+lvl*.4;
        X.beginPath();X.moveTo(5,0);X.lineTo(16+lvl*2,0);X.stroke();
        const prR=5+lvl*2;
        X.fillStyle=def.color+'50';X.strokeStyle=def.color;X.lineWidth=1.5;
        X.beginPath();X.moveTo(16+lvl*2+prR,0);X.lineTo(16+lvl*2,-prR*.7);X.lineTo(16+lvl*2-prR*.3,0);X.lineTo(16+lvl*2,prR*.7);X.closePath();X.fill();X.stroke();
        if(lvl>=1){const rx=16+lvl*2;X.strokeStyle=def.color+'35';X.lineWidth=.8;X.beginPath();X.arc(rx,0,prR+2+Math.sin(gt*.08)*1.5,0,TAU);X.stroke();}
        if(lvl>=2){X.fillStyle=def.color+'35';X.fillRect(7,-7-lvl,5,3);X.fillRect(7,4+lvl,5,3);X.strokeStyle=def.color+'50';X.lineWidth=1;X.strokeRect(7,-7-lvl,5,3);X.strokeRect(7,4+lvl,5,3);}
        if(lvl>=3){X.strokeStyle=def.color;X.lineWidth=1.5;X.beginPath();X.moveTo(8,-4);X.lineTo(16,-2);X.stroke();X.beginPath();X.moveTo(8,4);X.lineTo(16,2);X.stroke();}
        break;
      }

      case 10: // PLASMA
        X.strokeStyle=def.color;X.lineWidth=2;
        X.beginPath();X.moveTo(5,0);X.lineTo(16+lvl*2,0);X.stroke();
        {const orR=4+lvl*1.5;const ox=16+lvl*2;
        const og=X.createRadialGradient(ox,0,0,ox,0,orR);
        og.addColorStop(0,'#ffffff80');og.addColorStop(.4,def.color+'80');og.addColorStop(1,def.color+'00');
        X.fillStyle=og;X.beginPath();X.arc(ox,0,orR+Math.sin(gt*.06)*1.5,0,TAU);X.fill();}
        if(lvl>=2){X.strokeStyle=def.color+'40';X.lineWidth=1;X.beginPath();X.arc(10,0,6+lvl,0,TAU);X.stroke();}
        break;

      case 11: // DISRUPTOR
        X.strokeStyle=def.color;X.lineWidth=2;
        X.beginPath();X.moveTo(4,0);X.lineTo(12+lvl,0);X.stroke();
        {const dr=8+lvl*2;
        X.fillStyle=def.color+'20';X.strokeStyle=def.color;X.lineWidth=1.5;
        X.beginPath();X.arc(12+lvl,0,dr,-PI*.4,PI*.4);X.lineTo(12+lvl,0);X.closePath();X.fill();X.stroke();
        if(lvl>=1){X.strokeStyle=def.color+'30';X.lineWidth=1;X.beginPath();X.arc(12+lvl,0,dr+3,-PI*.3,PI*.3);X.stroke();}
        if(lvl>=2){X.beginPath();X.arc(12+lvl,0,dr+6,-PI*.2,PI*.2);X.stroke();}}
        break;

      case 12: // TESLA
        X.strokeStyle=def.color;X.lineWidth=2;
        {const th=14+lvl*3;
        X.beginPath();X.moveTo(-2,0);X.lineTo(-2,-th*.3);X.lineTo(2,-th*.3);X.lineTo(2,0);X.stroke();
        X.fillStyle=def.color+'40';X.beginPath();X.arc(0,-th*.3,4+lvl,0,TAU);X.fill();X.stroke();
        X.fillStyle=def.color;X.beginPath();X.arc(0,-th*.3,2,0,TAU);X.fill();
        if(lvl>=1){for(let i=0;i<3+lvl;i++){const a=gt*.06+i*TAU/(3+lvl);const ar=5+lvl+Math.sin(gt*.1+i)*2;X.strokeStyle=def.color+'50';X.lineWidth=.8;X.beginPath();X.arc(Math.cos(a)*ar,-th*.3+Math.sin(a)*ar,1.5,0,TAU);X.stroke();}}}
        break;

      case 13: // RAILGUN
        X.strokeStyle=def.color;X.lineWidth=4+lvl;
        X.beginPath();X.moveTo(4,0);X.lineTo(26+lvl*4,0);X.stroke();
        X.strokeStyle=def.color+'60';X.lineWidth=1;
        X.beginPath();X.moveTo(4,-3-lvl*.5);X.lineTo(26+lvl*4,-2-lvl*.3);X.stroke();
        X.beginPath();X.moveTo(4,3+lvl*.5);X.lineTo(26+lvl*4,2+lvl*.3);X.stroke();
        X.strokeStyle=def.color+'40';X.lineWidth=1;
        for(let i=0;i<2+lvl;i++){const ccx=8+i*(14+lvl)/(2+lvl);X.beginPath();X.arc(ccx,0,3+lvl*.5,0,TAU);X.stroke();}
        {const mzX=26+lvl*4,mzP=2+Math.sin(gt*.06)*1.5;X.fillStyle=def.color;X.beginPath();X.arc(mzX,0,mzP,0,TAU);X.fill();}
        if(lvl>=2){X.fillStyle=def.color+'25';X.strokeStyle=def.color+'60';X.lineWidth=1;X.beginPath();X.moveTo(2,-7);X.lineTo(10,-5);X.lineTo(10,-8);X.lineTo(2,-10);X.closePath();X.fill();X.stroke();X.beginPath();X.moveTo(2,7);X.lineTo(10,5);X.lineTo(10,8);X.lineTo(2,10);X.closePath();X.fill();X.stroke();}
        break;

      case 14: // EMP
        X.strokeStyle=def.color;X.lineWidth=1.5;X.fillStyle=def.color+'25';
        {const er=9+lvl*2;
        X.beginPath();X.arc(0,-2,er,PI,TAU);X.closePath();X.fill();X.stroke();
        X.fillStyle=def.color;X.beginPath();X.arc(0,-2,2+lvl,0,TAU);X.fill();
        const pulseR=er+3+Math.sin(gt*.08)*3;
        X.strokeStyle=def.color+'20';X.lineWidth=1;X.beginPath();X.arc(0,-2,pulseR,PI,TAU);X.stroke();
        if(lvl>=2){X.strokeStyle=def.color+'15';X.beginPath();X.arc(0,-2,pulseR+5,PI,TAU);X.stroke();}}
        break;

      case 15: // ACID
        X.strokeStyle=def.color;X.lineWidth=2;
        X.beginPath();X.moveTo(5,0);X.lineTo(16+lvl*2,0);X.stroke();
        X.fillStyle=def.color+'30';X.strokeStyle=def.color;X.lineWidth=1.5;
        X.beginPath();X.moveTo(16+lvl*2,-4-lvl);X.lineTo(20+lvl*2,-4-lvl);X.lineTo(22+lvl*2,0);X.lineTo(20+lvl*2,4+lvl);X.lineTo(16+lvl*2,4+lvl);X.closePath();X.fill();X.stroke();
        if(lvl>=1){const dy=4+lvl+Math.sin(gt*.08)*2;X.fillStyle=def.color+'60';X.beginPath();X.arc(22+lvl*2,dy,1.5,0,TAU);X.fill();}
        break;

      case 16: // PLAGUE
        X.strokeStyle=def.color;X.lineWidth=2;
        X.beginPath();X.moveTo(3,0);X.lineTo(3,-8-lvl*2);X.stroke();
        X.fillStyle=def.color+'25';X.beginPath();X.arc(3,-8-lvl*2,5+lvl,0,TAU);X.fill();X.stroke();
        for(let i=0;i<2+lvl;i++){
          const pa=gt*.03+i*1.5;const pr2=6+lvl+Math.sin(pa)*3;
          X.fillStyle=def.color+'20';X.beginPath();X.arc(3+Math.cos(pa)*pr2,-8-lvl*2+Math.sin(pa)*pr2*.5-3,2+Math.random(),0,TAU);X.fill();
        }
        break;

      case 17: // VENOM
        X.strokeStyle=def.color;X.lineWidth=2;
        X.beginPath();X.moveTo(5,0);X.lineTo(22+lvl*3,0);X.stroke();
        X.lineWidth=1;X.beginPath();X.moveTo(22+lvl*3,0);X.lineTo(26+lvl*3,-1);X.lineTo(26+lvl*3,1);X.closePath();X.fill();X.stroke();
        X.fillStyle=def.color+'30';X.strokeStyle=def.color;X.lineWidth=1.5;
        X.beginPath();X.moveTo(8,-4-lvl);X.lineTo(16,-4-lvl);X.lineTo(16,4+lvl);X.lineTo(8,4+lvl);X.closePath();X.fill();X.stroke();
        if(lvl>=1){X.fillStyle=def.color+'60';X.fillRect(10,-2-lvl*.5,4,4+lvl);}
        break;

      case 18: // MINT
        X.fillStyle='#ffd700'+'40';X.strokeStyle='#ffd700';X.lineWidth=1.5;
        X.beginPath();X.arc(0,0,8+lvl*2,0,TAU);X.fill();X.stroke();
        X.fillStyle='#ffd700';X.font=`${10+lvl*2}px serif`;X.textAlign='center';X.textBaseline='middle';
        X.fillText('$',0,1);
        if(lvl>=1){for(let ci=0;ci<3+lvl;ci++){const ca=ci/6*TAU+gt*.02;X.fillStyle='#ffd700'+'60';X.beginPath();X.arc(Math.cos(ca)*(12+lvl*2),Math.sin(ca)*(12+lvl*2),1.5,0,TAU);X.fill();}}
        break;

      case 19: // BANK
        X.fillStyle='#ffd700'+'30';X.strokeStyle='#ffd700';X.lineWidth=2;
        X.beginPath();X.moveTo(-10-lvl,-8-lvl);X.lineTo(10+lvl,-8-lvl);X.lineTo(12+lvl,8+lvl);X.lineTo(-12-lvl,8+lvl);X.closePath();X.fill();X.stroke();
        X.fillStyle='#ffd700';X.font=`${12+lvl*2}px serif`;X.textAlign='center';X.textBaseline='middle';
        X.fillText('$',0,1);
        X.strokeStyle='#ffd700'+'80';X.lineWidth=1;X.beginPath();X.moveTo(-8-lvl,-8-lvl);X.lineTo(8+lvl,-8-lvl);X.stroke();
        if(lvl>=2){X.fillStyle='#ffd700'+'40';for(let ci=0;ci<4;ci++){const ca=ci/4*TAU+gt*.015;X.beginPath();X.arc(Math.cos(ca)*(14+lvl*2),Math.sin(ca)*(14+lvl*2),2,0,TAU);X.fill();}}
        break;

      case 20: // MEGACORP
        X.fillStyle='#ffd700'+'25';X.strokeStyle='#ffd700';X.lineWidth=2.5;
        X.beginPath();X.moveTo(0,-14-lvl*2);X.lineTo(12+lvl*2,7+lvl);X.lineTo(-12-lvl*2,7+lvl);X.closePath();X.fill();X.stroke();
        X.fillStyle='#ffd700';X.font=`bold ${14+lvl*2}px serif`;X.textAlign='center';X.textBaseline='middle';
        X.fillText('$',0,2);
        for(let ri=0;ri<2+lvl;ri++){const ra=gt*.03+ri*TAU/3;X.strokeStyle='#ffd700'+'50';X.lineWidth=1;X.beginPath();X.arc(0,0,16+ri*4+lvl*2,ra,ra+.5);X.stroke();}
        break;
    }

    // === CENTER CORE ===
    X.shadowBlur=0;
    X.rotate(-ang); // un-rotate for core
    const coreR = 3.5 + lvl * 0.8 + Math.sin(gt*.04)*.8;
    // Outer core ring
    X.strokeStyle = def.color + '60';
    X.lineWidth = 1;
    X.beginPath(); X.arc(0,0,coreR+2,0,TAU); X.stroke();
    // Core fill
    const coreGrad = X.createRadialGradient(0,0,0,0,0,coreR+1);
    coreGrad.addColorStop(0, '#ffffff');
    coreGrad.addColorStop(.4, def.color);
    coreGrad.addColorStop(1, def.color+'00');
    X.fillStyle=coreGrad;
    X.beginPath(); X.arc(0,0,coreR+1,0,TAU); X.fill();

    // Spinning energy at lvl 3
    if (lvl>=3) {
      X.strokeStyle=def.color+'50'; X.lineWidth=1;
      for(let i=0;i<4;i++){
        const a = gt*.03+i*PI/2;
        X.beginPath();
        X.arc(0,0,baseR*.7, a, a+.3);
        X.stroke();
      }
    }

    X.restore();

    // === LEVEL STARS ===
    for (let l=0;l<lvl;l++){
      const sx = px - (lvl-1)*5 + l*10;
      const sy = py + baseR + 6;
      X.save(); X.translate(sx,sy);
      X.fillStyle=def.color; X.shadowColor=def.color; X.shadowBlur=4;
      X.beginPath();
      for(let i=0;i<5;i++){
        const a=(i/5)*TAU-PI/2;
        const sa=(i+.5)/5*TAU-PI/2;
        X.lineTo(Math.cos(a)*3.5, Math.sin(a)*3.5);
        X.lineTo(Math.cos(sa)*1.5, Math.sin(sa)*1.5);
      }
      X.closePath(); X.fill();
      X.shadowBlur=0; X.restore();
    }

    // === LASER BEAM ===
    if (def.beam && t.target && (t.beamAlpha||0)>.04) {
      X.save();
      const ba = (t.beamAlpha||1)*(.65+Math.sin(gt*.25)*.35);
      X.globalAlpha = ba;
      // Outer beam glow
      X.shadowColor=def.color; X.shadowBlur=20+lvl*5;
      X.strokeStyle=def.color+'60'; X.lineWidth=4+lvl*2;
      X.beginPath();
      X.moveTo(px+Math.cos(t.angle)*(19+lvl*2), py+Math.sin(t.angle)*(19+lvl*2));
      X.lineTo(t.target.x,t.target.y);
      X.stroke();
      // Core beam
      X.strokeStyle=def.color; X.lineWidth=2+lvl;
      X.beginPath();
      X.moveTo(px+Math.cos(t.angle)*(19+lvl*2), py+Math.sin(t.angle)*(19+lvl*2));
      X.lineTo(t.target.x,t.target.y);
      X.stroke();
      // White core
      X.strokeStyle='#fff'; X.lineWidth=1;
      X.beginPath();
      X.moveTo(px+Math.cos(t.angle)*(19+lvl*2), py+Math.sin(t.angle)*(19+lvl*2));
      X.lineTo(t.target.x,t.target.y);
      X.stroke();
      X.shadowBlur=0; X.restore();
    }

    // === SELECTED RING ===
    if (selectedTower===t) {
      X.strokeStyle='#fff'; X.lineWidth=1; X.setLineDash([4,4]);
      X.beginPath(); X.arc(px,py,baseR+6,0,TAU); X.stroke(); X.setLineDash([]);
    }
  });
}

function drawEnemies(alpha) {
  enemies.forEach(e => {
    const ex = lerp(e.prevX||e.x, e.x, alpha);
    const ey = lerp(e.prevY||e.y, e.y, alpha);
    const col = enemyColor(e);
    const r = enemyRadius(e);

    // Movement direction for rotation
    const dx = e.x - (e.prevX||e.x);
    const dy = e.y - (e.prevY||e.y);
    const moveAngle = Math.atan2(dy, dx);

    // Glow
    const glow = X.createRadialGradient(ex,ey,0,ex,ey,r*3);
    glow.addColorStop(0,col+'30');
    glow.addColorStop(.5,col+'10');
    glow.addColorStop(1,col+'00');
    X.fillStyle=glow;
    X.beginPath(); X.arc(ex,ey,r*3,0,TAU); X.fill();

    X.save(); X.translate(ex,ey);
    X.shadowColor=col; X.shadowBlur=14;
    if (e.type==='stealth' && !e.visible) X.globalAlpha=.15;

    switch(e.type) {
      case 'normal': {
        X.rotate(moveAngle);
        // Diamond body
        X.strokeStyle=col; X.lineWidth=2;
        X.fillStyle=col+'20';
        X.beginPath();
        X.moveTo(r+2, 0);
        X.lineTo(0, -r*.75);
        X.lineTo(-r*.8, 0);
        X.lineTo(0, r*.75);
        X.closePath(); X.fill(); X.stroke();
        // Inner cross
        X.strokeStyle=col+'50'; X.lineWidth=1;
        X.beginPath(); X.moveTo(-r*.3,0); X.lineTo(r*.5,0); X.stroke();
        X.beginPath(); X.moveTo(0,-r*.35); X.lineTo(0,r*.35); X.stroke();
        // Engine dot
        X.fillStyle=col;
        X.beginPath(); X.arc(-r*.4,0,1.5,0,TAU); X.fill();
        break;
      }
      case 'fast': {
        X.rotate(moveAngle);
        // Sleek arrow body
        X.strokeStyle=col; X.lineWidth=1.8;
        X.fillStyle=col+'18';
        X.beginPath();
        X.moveTo(r+4,0);
        X.lineTo(r*.2,-r*.4);
        X.lineTo(-r*.3,-r*.7);
        X.lineTo(-r*.8,-r*.3);
        X.lineTo(-r*.5, 0);
        X.lineTo(-r*.8, r*.3);
        X.lineTo(-r*.3, r*.7);
        X.lineTo(r*.2, r*.4);
        X.closePath(); X.fill(); X.stroke();
        // Speed lines
        X.strokeStyle=col+'40'; X.lineWidth=1;
        X.beginPath(); X.moveTo(-r*.5,-r*.15); X.lineTo(-r*1.2,-r*.15); X.stroke();
        X.beginPath(); X.moveTo(-r*.5, r*.15); X.lineTo(-r*1.2, r*.15); X.stroke();
        // Nose tip
        X.fillStyle=col;
        X.beginPath(); X.arc(r+2,0,2,0,TAU); X.fill();
        break;
      }
      case 'tank': {
        X.rotate(moveAngle);
        // Heavy armored hex with inner structure
        X.strokeStyle=col; X.lineWidth=2.8;
        X.fillStyle=col+'20';
        X.beginPath();
        for(let i=0;i<6;i++){const a=(i/6)*TAU; X.lineTo(Math.cos(a)*r,Math.sin(a)*r);}
        X.closePath(); X.fill(); X.stroke();
        // Armor plates (inner hex)
        X.strokeStyle=col+'60'; X.lineWidth=1.5;
        X.beginPath();
        for(let i=0;i<6;i++){const a=(i/6)*TAU+PI/6; X.lineTo(Math.cos(a)*r*.6,Math.sin(a)*r*.6);}
        X.closePath(); X.stroke();
        // Connect inner to outer
        for(let i=0;i<6;i++){
          const a=(i/6)*TAU;
          X.strokeStyle=col+'30'; X.lineWidth=1;
          X.beginPath(); X.moveTo(Math.cos(a)*r*.55,Math.sin(a)*r*.55);
          X.lineTo(Math.cos(a)*r*.9,Math.sin(a)*r*.9); X.stroke();
        }
        // Core
        X.fillStyle=col; X.beginPath(); X.arc(0,0,3,0,TAU); X.fill();
        // Heavy cannon forward
        X.strokeStyle=col; X.lineWidth=3;
        X.beginPath(); X.moveTo(r*.4,0); X.lineTo(r+4,0); X.stroke();
        break;
      }
      case 'shield': {
        X.rotate(moveAngle);
        // Core sphere
        X.strokeStyle=col; X.lineWidth=1.8;
        X.fillStyle=col+'25';
        X.beginPath(); X.arc(0,0,r,0,TAU); X.fill(); X.stroke();
        // Inner pattern
        X.strokeStyle=col+'40'; X.lineWidth=1;
        X.beginPath(); X.arc(0,0,r*.5,0,TAU); X.stroke();
        X.beginPath(); X.moveTo(-r*.5,0); X.lineTo(r*.5,0); X.stroke();
        X.beginPath(); X.moveTo(0,-r*.5); X.lineTo(0,r*.5); X.stroke();
        // Shield energy ring
        if (e.shield > 0) {
          const shPct = e.shield / e.maxShield;
          X.shadowColor='#00ddff'; X.shadowBlur=18;
          // Outer shield hexagonal
          X.strokeStyle='#00ddff'; X.lineWidth=2;
          const shieldR = r + 5;
          const shArc = shPct * TAU;
          X.beginPath(); X.arc(0,0,shieldR,-PI/2,-PI/2+shArc); X.stroke();
          // Shield particles
          for(let i=0;i<4;i++){
            const a = -PI/2 + shArc * (i/4) + gt*.02;
            if(a < -PI/2+shArc) {
              X.fillStyle='#00ddff50';
              X.beginPath(); X.arc(Math.cos(a)*shieldR,Math.sin(a)*shieldR,1.5,0,TAU); X.fill();
            }
          }
        }
        break;
      }
      case 'swarm': {
        X.rotate(moveAngle);
        X.strokeStyle=col; X.lineWidth=1.5; X.fillStyle=col+'30';
        X.beginPath(); X.arc(0,0,r,0,TAU); X.fill(); X.stroke();
        X.fillStyle=col; X.beginPath(); X.arc(1,0,1.5,0,TAU); X.fill();
        break;
      }
      case 'splitter': {
        X.rotate(moveAngle);
        X.strokeStyle=col; X.lineWidth=2; X.fillStyle=col+'20';
        X.beginPath(); X.moveTo(r+2,0); X.lineTo(0,-r); X.lineTo(-r*.5,-r*.3);
        X.lineTo(-r*.5,r*.3); X.lineTo(0,r); X.closePath(); X.fill(); X.stroke();
        X.strokeStyle=col+'50'; X.lineWidth=1;
        X.beginPath(); X.moveTo(-2,-r*.4); X.lineTo(-2,r*.4); X.stroke();
        break;
      }
      case 'armored': {
        X.rotate(moveAngle);
        X.strokeStyle=col; X.lineWidth=3; X.fillStyle=col+'25';
        X.beginPath(); for(let i=0;i<6;i++){const a=(i/6)*TAU;X.lineTo(Math.cos(a)*r,Math.sin(a)*r);} X.closePath(); X.fill(); X.stroke();
        X.strokeStyle=col+'60'; X.lineWidth=2;
        X.beginPath(); for(let i=0;i<6;i++){const a=(i/6)*TAU+PI/6;X.lineTo(Math.cos(a)*r*.5,Math.sin(a)*r*.5);} X.closePath(); X.stroke();
        X.strokeStyle=col; X.lineWidth=2; X.beginPath(); X.moveTo(r*.3,0); X.lineTo(r+3,0); X.stroke();
        break;
      }
      case 'healer': {
        X.strokeStyle=col; X.lineWidth=1.8; X.fillStyle=col+'25';
        X.beginPath(); X.arc(0,0,r,0,TAU); X.fill(); X.stroke();
        // Cross symbol
        X.strokeStyle=col; X.lineWidth=2.5;
        X.beginPath(); X.moveTo(-r*.5,0); X.lineTo(r*.5,0); X.stroke();
        X.beginPath(); X.moveTo(0,-r*.5); X.lineTo(0,r*.5); X.stroke();
        // Heal aura
        const ha=r+4+Math.sin(gt*.04)*2;
        X.strokeStyle=col+'30'; X.lineWidth=1; X.beginPath(); X.arc(0,0,ha,0,TAU); X.stroke();
        break;
      }
      case 'regen': {
        X.rotate(moveAngle);
        X.strokeStyle=col; X.lineWidth=2; X.fillStyle=col+'25';
        X.beginPath(); X.arc(0,0,r,0,TAU); X.fill(); X.stroke();
        // DNA helix
        X.strokeStyle=col+'70'; X.lineWidth=1;
        for(let i=0;i<6;i++){const yy=-r*.6+i*r*.24;X.beginPath();X.moveTo(Math.sin(gt*.04+i)*r*.4,yy);X.lineTo(Math.sin(gt*.04+i+PI)*r*.4,yy);X.stroke();}
        break;
      }
      case 'stealth': {
        X.rotate(moveAngle);
        X.strokeStyle=col; X.lineWidth=1.5; X.fillStyle=col+'15';
        X.beginPath(); X.moveTo(r+3,0); X.lineTo(-r*.4,-r*.8); X.lineTo(-r*.6,0); X.lineTo(-r*.4,r*.8); X.closePath(); X.fill(); X.stroke();
        X.strokeStyle=col+'40'; X.lineWidth=1; X.setLineDash([2,3]);
        X.beginPath(); X.arc(0,0,r+2,0,TAU); X.stroke(); X.setLineDash([]);
        break;
      }
      case 'boss': {
        // Rotating outer ring
        X.strokeStyle=col+'50'; X.lineWidth=2;
        X.beginPath();
        for(let i=0;i<12;i++){
          const a=(i/12)*TAU+gt*.005;
          const ir=i%2===0?r+3:r*.7;
          X.lineTo(Math.cos(a)*ir,Math.sin(a)*ir);
        }
        X.closePath(); X.fillStyle=col+'15'; X.fill(); X.stroke();

        // Inner body (counter-rotating)
        X.strokeStyle=col; X.lineWidth=2.5;
        X.fillStyle=col+'25';
        X.beginPath();
        for(let i=0;i<8;i++){
          const a=(i/8)*TAU-gt*.008;
          const ir=i%2===0?r*.7:r*.45;
          X.lineTo(Math.cos(a)*ir,Math.sin(a)*ir);
        }
        X.closePath(); X.fill(); X.stroke();

        // Core with gradient
        const cg = X.createRadialGradient(0,0,0,0,0,r*.35);
        cg.addColorStop(0,'#ffffff80');
        cg.addColorStop(.5,col+'80');
        cg.addColorStop(1,col+'00');
        X.fillStyle=cg;
        X.beginPath(); X.arc(0,0,r*.35,0,TAU); X.fill();

        // Orbiting energy dots
        for(let i=0;i<4;i++){
          const a = gt*.015+i*PI/2;
          const ox = Math.cos(a)*r*.55, oy = Math.sin(a)*r*.55;
          X.fillStyle=col;
          X.beginPath(); X.arc(ox,oy,2.5,0,TAU); X.fill();
        }

        // HP-based danger aura
        const hpPct = e.hp/e.maxHp;
        if (hpPct < .5) {
          X.strokeStyle=`rgba(255,0,0,${(.5-hpPct)*0.5})`; X.lineWidth=1;
          const ar = r+8+Math.sin(gt*.1)*3;
          X.beginPath(); X.arc(0,0,ar,0,TAU); X.stroke();
        }
        break;
      }
    }

    // Stealth fade
    if (e.type==='stealth' && !e.visible) X.globalAlpha=.15;

    // Stun indicator
    if (e.stunTimer > 0) {
      X.strokeStyle='rgba(255,255,0,.6)'; X.lineWidth=1.5; X.setLineDash([3,3]);
      X.beginPath(); X.arc(0,0,r+5,0,TAU); X.stroke(); X.setLineDash([]);
    }

    // DoT indicator
    if (e.dotDmg > 0) {
      X.fillStyle='rgba(68,255,0,.3)';
      for(let i=0;i<3;i++){const da=gt*.05+i*TAU/3;X.beginPath();X.arc(Math.cos(da)*(r+4),Math.sin(da)*(r+4),1,0,TAU);X.fill();}
    }

    // Slow indicator вЂ” icy ring
    if (e.slow > 0) {
      X.shadowBlur=8; X.shadowColor='#00aaff';
      X.strokeStyle='rgba(0,170,255,.5)'; X.lineWidth=1.5;
      X.setLineDash([2,4]);
      X.beginPath(); X.arc(0,0,r+7,0,TAU); X.stroke();
      X.setLineDash([]);
      // Ice crystals
      X.fillStyle='#00ccff40';
      for(let i=0;i<3;i++){
        const a=gt*.04+i*TAU/3;
        X.beginPath(); X.arc(Math.cos(a)*(r+7),Math.sin(a)*(r+7),1.5,0,TAU); X.fill();
      }
    }

    X.shadowBlur=0; X.restore();

    // HP bar with outline
    const bw=r*2.8, bh=3, bx=ex-bw/2, by=ey-r-12;
    X.fillStyle='rgba(0,0,0,.4)'; X.fillRect(bx-1,by-1,bw+2,bh+2);
    X.fillStyle='rgba(255,0,0,.15)'; X.fillRect(bx,by,bw,bh);
    const hpPct = clamp(e.hp/e.maxHp,0,1);
    const hpCol = hpPct>.5 ? col : hpPct>.25 ? '#ff8800' : '#ff2200';
    X.fillStyle=hpCol; X.shadowColor=hpCol; X.shadowBlur=3;
    X.fillRect(bx,by,bw*hpPct,bh);
    X.shadowBlur=0;
  });
}

function enemyColor(e) {
  return {normal:'#ff00ff', fast:'#00ff88', tank:'#ff5500', shield:'#00ccff', boss:'#ff0044',
    healer:'#66ff66', splitter:'#ffaa00', stealth:'#8844ff', swarm:'#ff88ff',
    armored:'#cc8844', regen:'#00ff44'}[e.type]||'#ff00ff';
}
function enemyRadius(e) {
  return {fast:7, tank:14, boss:20, shield:10, normal:9,
    healer:10, splitter:11, stealth:8, swarm:5,
    armored:13, regen:9}[e.type]||9;
}

function drawProjectiles(alpha) {
  projectiles.forEach(p => {
    p.trail.forEach(t => {
      const a=t.life/6;
      X.globalAlpha=a*.35; X.fillStyle=p.color;
      X.beginPath(); X.arc(t.x,t.y,p.size*a,0,TAU); X.fill();
    });
    X.globalAlpha=1;
    X.shadowColor=p.color; X.shadowBlur=10;
    X.fillStyle=p.color;
    X.beginPath(); X.arc(p.x,p.y,p.size,0,TAU); X.fill();
    X.fillStyle='#fff';
    X.beginPath(); X.arc(p.x,p.y,p.size*.4,0,TAU); X.fill();
    X.shadowBlur=0;
  });
}

function drawParticles(alpha) {
  particles.forEach(p => {
    const a=p.life/p.maxLife;
    X.globalAlpha=a;
    X.fillStyle=p.color; X.shadowColor=p.color; X.shadowBlur=5;
    X.beginPath(); X.arc(p.x,p.y,p.size*a,0,TAU); X.fill();
  });
  X.globalAlpha=1; X.shadowBlur=0;
}

function drawFloatTexts() {
  floatTexts.forEach(f => {
    X.globalAlpha=clamp(f.life/25,0,1);
    X.font='bold 13px monospace';
    X.fillStyle=f.color; X.shadowColor=f.color; X.shadowBlur=6;
    X.textAlign='center'; X.fillText(f.text,f.x,f.y);
  });
  X.globalAlpha=1; X.shadowBlur=0;
}

function drawGhostPreview() {
  if (selectedDef<0||!hoverCell) return;
  const def=TDEFS[selectedDef];
  const px=hoverCell.cx*CELL+CELL/2, py=hoverCell.cy*CELL+CELL/2;
  const ok=canPlace(hoverCell.cx,hoverCell.cy);

  X.globalAlpha=.18;
  X.fillStyle=ok?def.color:'#ff0000';
  X.beginPath(); X.arc(px,py,def.range,0,TAU); X.fill();
  X.globalAlpha=.55;
  X.strokeStyle=ok?def.color:'#ff0000'; X.lineWidth=2;
  X.beginPath();
  for(let i=0;i<6;i++){const a=(i/6)*TAU-PI/6; X.lineTo(px+Math.cos(a)*17,py+Math.sin(a)*17);}
  X.closePath(); X.stroke();
  X.globalAlpha=1;
}

function drawRangeCircle() {
  if (!selectedTower) return;
  X.strokeStyle='rgba(255,255,255,.12)'; X.lineWidth=1; X.setLineDash([5,5]);
  X.beginPath(); X.arc(selectedTower.x,selectedTower.y,selectedTower.range,0,TAU); X.stroke();
  X.setLineDash([]);
}

function drawVignette() {
  const w=W(), h=H();
  const grd=X.createRadialGradient(w/2,h/2,h*.28,w/2,h/2,h*.88);
  grd.addColorStop(0,'rgba(0,0,0,0)');
  grd.addColorStop(1,'rgba(0,0,0,.5)');
  X.fillStyle=grd; X.fillRect(0,0,w,h);
}

function drawScanlines() {
  X.globalAlpha=.02; X.fillStyle='#000';
  for(let y=0;y<H();y+=3) X.fillRect(0,y,W(),1);
  X.globalAlpha=1;
}

// =============================================================
//  HUD
// =============================================================
function updateHUD() {
  document.getElementById('gold-display').textContent=`GOLD: ${gold}`;
  document.getElementById('lives-display').textContent=`LIVES: ${lives}`;
  document.getElementById('wave-display').textContent=`WAVE: ${wave} / ${TOTAL_WAVES}`;
  document.getElementById('score-display').textContent=`SCORE: ${score.toLocaleString()}`;

  document.querySelectorAll('.tower-card').forEach(c => {
    const idx = parseInt(c.dataset.idx);
    const actualCost = Math.round(TDEFS[idx].cost*(1-buffMods.towerDiscount));
    c.style.opacity = gold >= actualCost ? '1' : '.4';
    c.classList.toggle('selected', selectedDef === idx);
  });

  if (selectedTower) {
    const t=selectedTower, def=TDEFS[t.type];
    document.getElementById('info-panel').style.display='block';
    document.getElementById('ip-title').textContent=def.name+(t.level>0?` в…${t.level}`:'');
    if(def.farm){
      const fi=Math.round((t.farm||def.farm)*buffMods.farmMul);
      document.getElementById('ip-dmg').textContent=`${fi}G/wave`;
      document.getElementById('ip-rate').textContent='FARM';
      document.getElementById('ip-range').textContent='-';
    } else {
      document.getElementById('ip-dmg').textContent=t.dmg<1?t.dmg.toFixed(2):Math.round(t.dmg);
      document.getElementById('ip-rate').textContent=(60/t.rate).toFixed(1)+'/s';
      document.getElementById('ip-range').textContent=Math.round(t.range);
    }
    document.getElementById('ip-lvl').textContent=`${t.level} / 3`;

    document.getElementById('tower-actions').style.display='flex';
    const upg=def.upgrades[t.level];
    const ub=document.getElementById('upgrade-btn');
    if(upg){
      const upgCost=buffMods.freeUpgrades?0:Math.round(upg.cost*(1-buffMods.upgradeDiscount));
      ub.textContent=`UPGRADE (${upgCost}G)`;ub.style.display='block';ub.style.opacity=gold>=upgCost?'1':'.4';
    }
    else ub.style.display='none';

    let totalCost = def.cost;
    for (let i=0;i<t.level;i++) totalCost += def.upgrades[i].cost;
    const sellPct=buffMods.sellRefund||.6;
    const refund = Math.floor(totalCost*sellPct);
    document.getElementById('sell-btn').textContent=`SELL (+${refund}G)`;
  } else {
    document.getElementById('info-panel').style.display='none';
    document.getElementById('tower-actions').style.display='none';
  }
}

// =============================================================
//  INPUT
// =============================================================
C.addEventListener('mousemove',e=>{
  hoverCell={cx:Math.floor(e.clientX/CELL),cy:Math.floor(e.clientY/CELL)};
});

C.addEventListener('click',e=>{
  const cx=Math.floor(e.clientX/CELL), cy=Math.floor(e.clientY/CELL);

  if (selectedDef>=0) {
    if(buffMods.buildBanWaves>0){addFloat(W()/2,H()/2,'BUILD BANNED!','#ff4466');return;}
    const def=TDEFS[selectedDef];
    const actualCost=Math.round(def.cost*(1-buffMods.towerDiscount));
    if (gold>=actualCost && canPlace(cx,cy)) {
      towers.push({
        type:selectedDef, cx, cy,
        x:cx*CELL+CELL/2, y:cy*CELL+CELL/2,
        range:Math.round(def.range*buffMods.rangeMul), rate:def.rate, dmg:def.dmg,
        splash:def.splash, slow:def.slow,
        dot:def.dot||0, chain:def.chain||0,
        farm:def.farm||0,
        cooldown:0, angle:0, level:0, target:null, beamAlpha:0,
      });
      gold-=actualCost;
      sfxPlace();
      spawnP(cx*CELL+CELL/2, cy*CELL+CELL/2, 8, def.color, 3, 16, 2);
    }
    return;
  }

  const clicked=towers.find(t=>t.cx===cx&&t.cy===cy);
  selectedTower = clicked||null;
  selectedDef=-1;
});

C.addEventListener('contextmenu',e=>{e.preventDefault();selectedDef=-1;selectedTower=null;});

addEventListener('keydown',e=>{
  if(e.key==='Escape'){selectedDef=-1;selectedTower=null;closeCasino();closeTechTree();}
  if(e.key==='q'||e.key==='Q'||e.key==='Р№'||e.key==='Р™') useAbility(0);
  if(e.key==='w'||e.key==='W'||e.key==='С†'||e.key==='Р¦') useAbility(1);
});

function selectTower(idx){selectedTower=null;selectedDef=selectedDef===idx?-1:idx;}

function upgradeTower(){
  if(!selectedTower)return;
  const t=selectedTower,def=TDEFS[t.type],upg=def.upgrades[t.level];
  if(!upg)return;
  const upgCost=buffMods.freeUpgrades?0:Math.round(upg.cost*(1-buffMods.upgradeDiscount));
  if(gold<upgCost)return;
  gold-=upgCost; t.level++;
  if(upg.dmg)t.dmg=upg.dmg;
  if(upg.range)t.range=Math.round(upg.range*buffMods.rangeMul);
  if(upg.rate)t.rate=upg.rate;
  if(upg.splash)t.splash=upg.splash;
  if(upg.slow)t.slow=upg.slow;
  if(upg.dot)t.dot=upg.dot;
  if(upg.chain)t.chain=upg.chain;
  if(upg.stun)t.stun=upg.stun;
  if(upg.farm)t.farm=upg.farm;
  sfxUpgrade();
  spawnP(t.x,t.y,12,TDEFS[t.type].color,4,18,3);
  addFloat(t.x,t.y,'в… UPGRADE','#00ffcc');
}

function sellTower(){
  if(!selectedTower)return;
  const t=selectedTower,def=TDEFS[t.type];
  let totalCost=def.cost;
  for(let i=0;i<t.level;i++) totalCost+=def.upgrades[i].cost;
  const sellPct=buffMods.sellRefund||.6;
  const refund=Math.floor(totalCost*sellPct);
  gold+=refund;
  spawnP(t.x,t.y,8,'#ffcc00',3,14,2);
  addFloat(t.x,t.y,`+${refund}G`,'#ffcc00');
  towers=towers.filter(tw=>tw!==t);
  selectedTower=null;
}

function sendNextWave(){
  if(wave>=TOTAL_WAVES)return;
  wave++;
  waveEnemies=waves[wave-1];
  spawnIdx=0;spawnTimer=0;waveActive=true;waveRPGiven=false;
  // Casino coin every 3 waves
  if(wave%3===0){
    casinoCoins++;
    updateCoinDisplay();
    addFloat(W()/2,H()/2+50,'рџЋ° +1 CASINO COIN!','#ff88ff');
    sfx(1200,.08,.04); sfx(1500,.06,.03);
  }
  // Extra coin every 5 waves buff
  if(buffMods.extraCoinEvery5 && wave%5===0){
    casinoCoins++;
    updateCoinDisplay();
    addFloat(W()/2,H()/2+70,'рџЋ° BONUS COIN!','#ffd700');
  }
  // Overcharge buff timer
  if(buffMods.overcharge) buffMods._overchargeTimer=900;
  // Build ban countdown
  if(buffMods.buildBanWaves>0) buffMods.buildBanWaves--;
  const el=document.getElementById('wave-announce');
  el.textContent=`WAVE ${wave}`;
  el.style.opacity='1';
  setTimeout(()=>el.style.opacity='0',2000);
}

// =============================================================
//  GAME LOOP вЂ” fixed timestep with interpolation
// =============================================================
let lastTime=0, acc=0;
const TICK = 1000/60;

function loop(ts) {
  if(!gameRunning) return;
  const dt = Math.min(ts-lastTime, 100); // cap dt
  lastTime=ts;
  acc+=dt;

  const ticksThisFrame = gameSpeed; // run extra ticks for speed-up
  for(let s=0;s<ticksThisFrame;s++){
    while(acc>=TICK){tick();acc-=TICK;}
    if(s<ticksThisFrame-1) acc+=TICK; // force extra tick for speed
  }

  const alpha = acc/TICK; // interpolation factor
  render(alpha);
  requestAnimationFrame(loop);
}

let autoWaveTimer=0, killCount=0;

function startGame(){
  initAudio();
  document.getElementById('menu-screen').style.display='none';
  document.getElementById('gameover-screen').style.display='none';
  document.getElementById('win-screen').style.display='none';
  document.getElementById('casino-overlay').style.display='none';
  document.getElementById('tech-overlay').style.display='none';
  resetState();
  buildTowerBar();
  buildPath();
  gameRunning=true;
  if(!musicPlaying) startMusic();
  lastTime=performance.now(); acc=0;
  requestAnimationFrame(loop);
}

function gameOver(){
  gameRunning=false;
  document.getElementById('gameover-screen').style.display='flex';
  document.getElementById('gameover-score').textContent=`SCORE: ${score.toLocaleString()}`;
  document.getElementById('gameover-wave').textContent=`WAVE REACHED: ${wave}`;
}

// Initial canvas size
resize();
