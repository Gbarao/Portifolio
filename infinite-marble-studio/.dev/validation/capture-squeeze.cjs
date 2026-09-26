const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const SP = process.env.SP;
const W = Number(process.env.W || 540),
  H = Number(process.env.H || 960);
const OUT = process.env.OUT || 'squeeze.png';
const SETTINGS = process.env.SETTINGS ? JSON.parse(process.env.SETTINGS) : null;
const FRACTIONS = (process.env.FR || 'rest,0,0.25,0.5,0.75,1,t0.66,t0.72').split(',');
(async () => {
  const browser = await chromium.launch({
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage({ viewport: { width: 800, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text());
  });
  await page.goto(`http://localhost:5174/lab/squeeze.html?t=0&w=${W}&h=${H}`, {
    waitUntil: 'load',
  });
  await page.waitForFunction(() => !!window.squeezeLab, null, { timeout: 60000 });
  const shots = await page.evaluate(
    async ({ fr, settings }) => {
      const lab = window.squeezeLab;
      if (settings) {
        const s = lab.settings;
        const merge = (a, b) => {
          for (const k of Object.keys(b)) {
            if (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k])) merge(a[k], b[k]);
            else a[k] = b[k];
          }
        };
        merge(s, settings);
        lab.rebuild(s);
      }
      const out = [];
      const canvas = document.querySelector('canvas');
      for (const f of fr) {
        let info;
        if (f === 'rest') info = lab.renderAt(0);
        else if (f.startsWith('t')) info = lab.renderAt(Number(f.slice(1)));
        else info = lab.renderPressure(Number(f));
        out.push({ f, info, url: canvas.toDataURL('image/png') });
      }
      return out;
    },
    { fr: FRACTIONS, settings: SETTINGS },
  );
  const tw = Math.min(W, 360),
    th = Math.round((tw * H) / W);
  await page.setViewportSize({ width: (tw + 6) * shots.length, height: th + 30 });
  await page.setContent(
    `<body style="margin:0;background:#111;color:#ddd;font:12px sans-serif;display:flex;gap:6px">${shots.map((s) => `<div><img src="${s.url}" width=${tw}><div>${s.f}</div></div>`).join('')}</body>`,
  );
  await page.screenshot({ path: `${SP}/${OUT}` });
  if (process.env.RAW) {
    const fs = require('fs');
    for (const s of shots)
      fs.writeFileSync(`${SP}/raw_${s.f}.png`, Buffer.from(s.url.split(',')[1], 'base64'));
  }
  for (const s of shots) console.log(s.f, s.info);
  console.log('errors', errors);
  await browser.close();
})();
