const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

function getArg(flag, defaultValue) {
  const index = process.argv.indexOf(flag);
  if (index !== -1 && index + 1 < process.argv.length) {
    return process.argv[index + 1];
  }
  return defaultValue;
}

const inputPath = getArg('--input');
const outputPath = getArg('--output');
const width = parseInt(getArg('--width', '720'), 10);
const height = parseInt(getArg('--height', '1280'), 10);
const fps = parseInt(getArg('--fps', '30'), 10);

if (!inputPath || !outputPath) {
  console.error(JSON.stringify({ error: 'Missing --input or --output argument' }));
  process.exit(1);
}

const sceneData = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
const duration = Number(sceneData.duration ?? 3.0);
if (!Number.isFinite(duration) || duration <= 0) throw new Error('Invalid scene duration');
const totalFrames = Math.max(1, Math.round(duration * fps));

// Read local font files as base64 for 100% offline determinism
const fontsDir = path.join(__dirname, 'fonts');
const barlowBold = fs.readFileSync(path.join(fontsDir, 'BarlowCondensed-Bold.ttf')).toString('base64');
const barlowExtraBold = fs.readFileSync(path.join(fontsDir, 'BarlowCondensed-ExtraBold.ttf')).toString('base64');
const interVar = fs.readFileSync(path.join(fontsDir, 'Inter-Variable.ttf')).toString('base64');

function buildHtml(data) {
  // All AI/user copy is literal text, never HTML or executable markup.
  const escape = value => typeof value === 'string' ? value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;') : value;
  const clean = value => Array.isArray(value) ? value.map(clean) : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([key, val]) => [key, key.endsWith('_path') ? val : clean(val)])) : escape(value);
  data = clean(data);
  const type = data.scene_type || 'explainer_card';
  const headline = data.headline || '';
  const subheadline = data.subheadline || '';
  const badgeText = data.badge_text || '';
  const badgeColor = data.badge_color || 'teal'; // teal, navy, red
  const statNumber = data.stat_number || '';
  const statLabel = data.stat_label || '';
  const steps = data.steps || [];
  const compLeft = data.comparison_left || { badge: '', title: '', points: [] };
  const compRight = data.comparison_right || { badge: '', title: '', points: [] };
  const footerText = data.footer || '';

  // Helper for image src: convert local path to base64 if exists
  function getImgSrc(p) {
    if (p && fs.existsSync(p)) {
      const ext = path.extname(p).toLowerCase();
      const mime = ext === '.svg' ? 'image/svg+xml' : ext === '.png' ? 'image/png' : 'image/jpeg';
      const b64 = fs.readFileSync(p).toString('base64');
      return `data:${mime};base64,${b64}`;
    }
    return '';
  }

  const assetSrc = getImgSrc(data.asset_path);
  const leftImgSrc = getImgSrc(compLeft.image_path);
  const rightImgSrc = getImgSrc(compRight.image_path);

  let sceneContent = '';

  if (type === 'explainer_card') {
    sceneContent = `
      ${badgeText ? `<div class="badge badge-${badgeColor} anim-badge">${badgeText}</div>` : ''}
      ${headline ? `<div class="headline anim-headline">${headline}</div>` : ''}
      <div class="card anim-card">
        ${assetSrc ? `<img src="${assetSrc}" class="card-img" />` : `
          <div class="procedural-graphic">
            <div class="mockup-header">
              <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
            </div>
            <div class="mockup-body">
              <div class="mockup-bar"></div>
              <div class="mockup-bar short"></div>
            </div>
          </div>
        `}
      </div>
      ${data.badges && data.badges.length ? `
        <div class="stagger-badges">
          ${data.badges.map((b, idx) => `<div class="badge badge-teal anim-stagger anim-delay-${idx}">☑ ${b}</div>`).join('')}
        </div>
      ` : ''}
      ${subheadline ? `<div class="subheadline anim-sub">${subheadline}</div>` : ''}
    `;
  } else if (type === 'comparison') {
    sceneContent = `
      ${headline ? `<div class="headline anim-headline">${headline}</div>` : '<div class="headline anim-headline">SO SÁNH BỐ CỤC</div>'}
      <div class="comparison-container anim-card">
        <div class="comp-col left">
          <div class="badge badge-teal">${compLeft.badge || 'LỰA CHỌN A'}</div>
          <div class="comp-title">${compLeft.title || ''}</div>
          ${leftImgSrc ? `<img src="${leftImgSrc}" class="comp-img" />` : ''}
          <div class="comp-points">
            ${(compLeft.points || []).map(pt => `<div class="comp-point">✔ ${pt}</div>`).join('')}
          </div>
        </div>
        <div class="comp-col right">
          <div class="badge badge-navy">${compRight.badge || 'LỰA CHỌN B'}</div>
          <div class="comp-title">${compRight.title || ''}</div>
          ${rightImgSrc ? `<img src="${rightImgSrc}" class="comp-img" />` : ''}
          <div class="comp-points">
            ${(compRight.points || []).map(pt => `<div class="comp-point">✔ ${pt}</div>`).join('')}
          </div>
        </div>
      </div>
    `;
  } else if (type === 'statistic') {
    sceneContent = `
      ${badgeText ? `<div class="badge badge-teal anim-badge">${badgeText}</div>` : '<div class="badge badge-teal anim-badge">SỐ LIỆU ĐÁNG CHÚ Ý</div>'}
      <div class="stat-number anim-stat">${statNumber}</div>
      <div class="stat-label anim-headline">${statLabel || headline}</div>
      <div class="card stat-card anim-card">
        ${assetSrc ? `<img src="${assetSrc}" class="card-img" />` : `
          <div class="stat-desc">${subheadline}</div>
        `}
      </div>
    `;
  } else if (type === 'step_list') {
    sceneContent = `
      ${headline ? `<div class="headline anim-headline">${headline}</div>` : '<div class="headline anim-headline">QUY TRÌNH THỰC HIỆN</div>'}
      <div class="steps-container">
        ${steps.map((st, i) => `
          <div class="step-row anim-stagger anim-delay-${i}">
            <div class="step-num">${i + 1}</div>
            <div class="badge badge-${i % 2 === 0 ? 'teal' : 'navy'} step-badge">${st.badge || st}</div>
            ${st.note ? `<div class="step-note">${st.note}</div>` : ''}
          </div>
        `).join('')}
      </div>
      ${data.warning_badge ? `<div class="badge badge-red anim-badge anim-delay-3">${data.warning_badge}</div>` : ''}
    `;
  } else if (type === 'cta') {
    sceneContent = `
      <div class="cta-avatar-ring anim-badge">
        ${assetSrc ? `<img src="${assetSrc}" class="cta-avatar" />` : `
          <div class="cta-avatar-placeholder">★</div>
        `}
      </div>
      <div class="cta-icon anim-delay-1">🔖</div>
      <div class="cta-button anim-card">
        ${headline || 'LƯU VIDEO NÀY LẠI'}
      </div>
      <div class="cta-sub anim-sub">
        ${subheadline}
      </div>
    `;
  } else if (type === 'talking_head_pip') {
    // White background, graphic on top, cutout container for speaker video at bottom
    sceneContent = `
      <div class="pip-top">
        ${badgeText ? `<div class="badge badge-${badgeColor} anim-badge">${badgeText}</div>` : ''}
        ${headline ? `<div class="headline anim-headline">${headline}</div>` : ''}
        <div class="card pip-card anim-card">
          ${assetSrc ? `<img src="${assetSrc}" class="card-img" />` : ''}
        </div>
        ${subheadline ? `<div class="badge badge-teal anim-stagger">${subheadline}</div>` : ''}
      </div>
      <div class="pip-speaker-container">
        <!-- Speaker video will be composited here by FFmpeg -->
      </div>
    `;
  }

  return `
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="utf-8">
    <style>
      @font-face {
        font-family: 'Barlow Condensed';
        font-weight: 700;
        src: url('data:font/ttf;base64,${barlowBold}') format('truetype');
      }
      @font-face {
        font-family: 'Barlow Condensed';
        font-weight: 800;
        src: url('data:font/ttf;base64,${barlowExtraBold}') format('truetype');
      }
      @font-face {
        font-family: 'Inter';
        src: url('data:font/ttf;base64,${interVar}') format('truetype');
      }

      * { box-sizing: border-box; }
      body {
        margin: 0;
        padding: 0;
        width: 720px;
        height: 1280px;
        background: #FFFFFF;
        font-family: 'Barlow Condensed', sans-serif;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        padding: 60px 40px 40px 40px;
        position: relative;
      }

      .main-content {
        width: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        flex: 1;
        gap: 20px;
      }

      /* Badges */
      .badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 10px 28px;
        border-radius: 9999px;
        color: #FFFFFF;
        font-size: 26px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
        max-width: 90%;
        text-align: center;
      }
      .badge-teal { background: #0D9488; }
      .badge-navy { background: #1E293B; }
      .badge-red { background: #DC2626; }

      /* Headlines */
      .headline {
        font-size: ${Math.max(18, Math.min(60, Number(data.headline_font_size) || 60))}px;
        white-space: pre-line;
        font-weight: 800;
        color: #1E293B;
        text-transform: uppercase;
        text-align: center;
        line-height: 1.15;
        max-width: 92%;
        letter-spacing: 0.5px;
      }
      .subheadline {
        font-family: 'Inter', sans-serif;
        font-size: 20px;
        font-weight: 600;
        color: #475569;
        text-align: center;
        max-width: 85%;
        line-height: 1.4;
      }

      /* Cards */
      .card {
        background: #FFFFFF;
        border-radius: 24px;
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.08), 0 2px 6px rgba(0,0,0,0.04);
        border: 1px solid #E2E8F0;
        padding: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        max-width: 88%;
        max-height: 480px;
        overflow: hidden;
      }
      .card-img {
        max-width: 100%;
        max-height: 440px;
        border-radius: 16px;
        object-fit: contain;
      }

      .stagger-badges {
        display: flex;
        flex-direction: column;
        gap: 12px;
        align-items: center;
        width: 100%;
      }

      /* Comparison */
      .comparison-container {
        display: flex;
        gap: 16px;
        width: 94%;
        padding: 18px;
        justify-content: space-between;
      }
      .comp-col {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        background: #F8FAFC;
        border-radius: 16px;
        padding: 16px 12px;
        border: 1px solid #E2E8F0;
      }
      .comp-title {
        font-size: 22px;
        font-weight: 800;
        color: #1E293B;
        text-align: center;
      }
      .comp-img {
        max-width: 100%;
        height: 140px;
        border-radius: 12px;
        object-fit: cover;
      }
      .comp-points {
        display: flex;
        flex-direction: column;
        gap: 8px;
        width: 100%;
      }
      .comp-point {
        font-family: 'Inter', sans-serif;
        font-size: 15px;
        font-weight: 600;
        color: #334155;
        line-height: 1.3;
      }

      /* Statistics */
      .stat-number {
        font-size: 96px;
        font-weight: 800;
        color: #0D9488;
        letter-spacing: -2px;
        line-height: 1;
        text-shadow: 0 8px 24px rgba(13, 148, 136, 0.2);
      }
      .stat-label {
        font-size: 34px;
        font-weight: 800;
        color: #1E293B;
        text-align: center;
      }
      .stat-card {
        padding: 24px;
      }
      .stat-desc {
        font-family: 'Inter', sans-serif;
        font-size: 18px;
        color: #475569;
        text-align: center;
        line-height: 1.4;
      }

      /* Steps */
      .steps-container {
        display: flex;
        flex-direction: column;
        gap: 16px;
        width: 88%;
      }
      .step-row {
        display: flex;
        align-items: center;
        gap: 16px;
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 18px;
        padding: 14px 20px;
      }
      .step-num {
        font-size: 40px;
        font-weight: 800;
        color: #94A3B8;
        line-height: 1;
        min-width: 32px;
      }
      .step-badge {
        font-size: 24px;
        padding: 8px 22px;
      }
      .step-note {
        font-family: 'Inter', sans-serif;
        font-size: 16px;
        color: #475569;
        font-weight: 600;
      }

      /* CTA */
      .cta-avatar-ring {
        width: 160px;
        height: 160px;
        border-radius: 50%;
        border: 5px solid #14B8A6;
        padding: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 16px 36px rgba(20, 184, 166, 0.25);
      }
      .cta-avatar {
        width: 100%;
        height: 100%;
        border-radius: 50%;
        object-fit: cover;
      }
      .cta-avatar-placeholder {
        font-size: 64px;
        color: #14B8A6;
      }
      .cta-icon {
        font-size: 48px;
      }
      .cta-button {
        background: #1E293B;
        color: #FFFFFF;
        font-size: 34px;
        font-weight: 800;
        padding: 16px 42px;
        border-radius: 9999px;
        letter-spacing: 1px;
        box-shadow: 0 12px 30px rgba(30, 41, 59, 0.3);
      }
      .cta-sub {
        font-family: 'Inter', sans-serif;
        font-size: 22px;
        font-weight: 600;
        color: #475569;
      }

      /* Talking Head PiP */
      .pip-top {
        position: absolute;
        top: 110px;
        left: 40px;
        height: 490px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 14px;
        width: 640px;
        justify-content: center;
      }
      .pip-card {
        max-height: 360px;
      }
      .pip-speaker-container {
        position: absolute;
        top: 627px;
        left: 36px;
        width: 90%;
        height: 550px;
        border-radius: 28px 28px 0 0;
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(6, 182, 212, 0.15));
        border: 3px solid #10B981;
        border-bottom: none;
      }

      .scene-explainer_card .card {max-height: 620px; max-width: 96%;}
      .scene-explainer_card .card-img {max-height: 580px;}
      /* Footer */
      .footer {
        font-family: 'Inter', sans-serif;
        font-size: 15px;
        font-weight: 700;
        color: #64748B;
        letter-spacing: 1px;
        display: flex;
        align-items: center;
        gap: 20px;
        padding-top: 10px;
      }

      /* Frame deterministic animation control */
      .anim-badge {
        transform: scale(var(--scale-badge, 1));
        opacity: var(--op-badge, 1);
      }
      .anim-headline {
        transform: translateY(var(--ty-headline, 0px));
        opacity: var(--op-headline, 1);
      }
      .anim-card {
        transform: scale(var(--scale-card, 1)) translateY(var(--ty-card, 0px));
        opacity: var(--op-card, 1);
      }
      .anim-stagger {
        transform: translateY(var(--ty-stagger, 0px));
        opacity: var(--op-stagger, 1);
      }
      .anim-sub {
        opacity: var(--op-sub, 1);
      }
      .anim-stat {
        transform: scale(var(--scale-stat, 1));
        opacity: var(--op-stat, 1);
      }
    </style>
  </head>
  <body class="scene-${type}">
    <div class="main-content">
      ${sceneContent}
    </div>
    <div class="footer">
      <span>${footerText}</span>
    </div>
  </body>
  </html>
  `;
}

async function render() {
  const candidates = [process.env.CHROME_PATH, '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'];
  const chromePath = candidates.find(p => p && fs.existsSync(p));
  if (!chromePath) throw new Error('Không tìm thấy Chrome/Chromium. Cài trình duyệt hoặc đặt CHROME_PATH tới executable.');
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage();
  // The same design coordinates keep preview and export layouts identical.
  await page.setViewport({ width: 720, height: 1280, deviceScaleFactor: 1 });
  const html = buildHtml(sceneData);
  await page.setContent(html, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);

  const ffmpeg = spawn('ffmpeg', [
    '-y',
    '-f', 'image2pipe',
    '-vcodec', 'png',
    '-r', fps.toString(),
    '-i', '-',
    '-vf', `scale=${width}:${height}`,
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-preset', 'ultrafast',
    '-threads', '2',
    '-movflags', '+faststart',
    outputPath
  ]);

  for (let f = 0; f < totalFrames; f++) {
    const t = f / fps; // current timestamp in seconds
    // Calculate smooth spring/ease animations
    await page.evaluate((cfg) => {
      const currTime = cfg.time;
      // Badge pop-in: 0.0s -> 0.35s
      const badgeT = Math.min(1, Math.max(0, currTime / 0.35));
      const badgeScale = badgeT < 1 ? 0.7 + 0.35 * Math.sin(badgeT * Math.PI) : 1;
      document.body.style.setProperty('--scale-badge', badgeScale);
      document.body.style.setProperty('--op-badge', Math.min(1, badgeT * 2));

      // Headline slide-down: 0.15s -> 0.5s
      const headT = Math.min(1, Math.max(0, (currTime - 0.15) / 0.35));
      document.body.style.setProperty('--ty-headline', `${(1 - headT) * -20}px`);
      document.body.style.setProperty('--op-headline', headT);

      // Card pop-in: 0.3s -> 0.7s
      const cardT = Math.min(1, Math.max(0, (currTime - 0.3) / 0.4));
      const cardScale = cardT < 1 ? 0.85 + 0.2 * Math.sin(cardT * Math.PI) : 1;
      document.body.style.setProperty('--scale-card', cardScale);
      document.body.style.setProperty('--ty-card', `${(1 - cardT) * 30}px`);
      document.body.style.setProperty('--op-card', Math.min(1, cardT * 1.5));

      // Stagger items: 0.5s onwards
      const stagT = Math.min(1, Math.max(0, (currTime - 0.5) / 0.4));
      document.body.style.setProperty('--ty-stagger', `${(1 - stagT) * 20}px`);
      document.body.style.setProperty('--op-stagger', stagT);
      document.querySelectorAll('.anim-stagger').forEach((el, index) => {
        const t = Math.min(1, Math.max(0, (currTime - 0.5 - index * 0.18) / 0.4));
        el.style.opacity = t;
        el.style.transform = `translateY(${(1-t)*20}px)`;
      });

      // Subtext fade
      const subT = Math.min(1, Math.max(0, (currTime - 0.6) / 0.4));
      document.body.style.setProperty('--op-sub', subT);

      // Stat pop
      const statT = Math.min(1, Math.max(0, (currTime - 0.2) / 0.4));
      document.body.style.setProperty('--scale-stat', statT < 1 ? 0.8 + 0.25 * Math.sin(statT * Math.PI) : 1);
      document.body.style.setProperty('--op-stat', statT);
      if (cfg.animation === 'fade' || cfg.animation === 'slide_up') {
        const entry = Math.min(1, currTime / .45);
        for (const el of document.querySelectorAll('.anim-badge, .anim-card, .anim-headline, .anim-stat, .anim-sub')) {
          el.style.opacity = entry;
          el.style.transform = cfg.animation === 'slide_up' ? `translateY(${(1-entry)*28}px)` : 'none';
        }
      }
      document.querySelector('.main-content').style.opacity = cfg.exit === 'fade' ? Math.min(1, Math.max(0, (cfg.duration-currTime)/.18)) : 1;
    }, {time: t, animation: sceneData.animation_in || 'pop_in', exit: sceneData.animation_out || 'none', duration});

    const buffer = await page.screenshot({ type: 'png' });
    if (!ffmpeg.stdin.write(buffer)) await new Promise(resolve => ffmpeg.stdin.once('drain', resolve));
  }

  ffmpeg.stdin.end();

  await new Promise((resolve, reject) => {
    ffmpeg.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`FFmpeg exited with code ${code}`));
    });
  });

  await browser.close();
  console.log(JSON.stringify({ status: 'success', frames: totalFrames, duration, output: outputPath }));
}

render().catch((err) => {
  console.error(JSON.stringify({ error: err.message, stack: err.stack }));
  process.exit(1);
});
