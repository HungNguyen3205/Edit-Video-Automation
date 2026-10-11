const puppeteer = require('puppeteer-core');
const fs = require('fs');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 720, height: 1280, deviceScaleFactor: 1 });

  const html = `
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800&family=Inter:wght@500;700&display=swap" rel="stylesheet">
    <style>
      body { margin: 0; background: #ffffff; width: 720px; height: 1280px; overflow: hidden; font-family: 'Barlow Condensed', sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; }
      .badge { background: #0D9488; color: white; padding: 12px 32px; border-radius: 9999px; font-size: 28px; font-weight: 800; letter-spacing: 1px; box-shadow: 0 8px 20px rgba(13,148,136,0.3); }
      .headline { font-size: 48px; color: #1E293B; margin-top: 24px; font-weight: 800; text-transform: uppercase; text-align: center; }
    </style>
  </head>
  <body>
    <div class="badge">ƯU ĐIỂM NỘI SÀN</div>
    <div class="headline">KHÁCH Ở RẤT GẦN<br/>HÀNH VI MUA</div>
  </body>
  </html>
  `;
  await page.setContent(html, { waitUntil: 'networkidle0' });
  await page.screenshot({ path: 'test_frame.png' });
  await browser.close();
  console.log('Frame rendered successfully, size:', fs.statSync('test_frame.png').size);
})();
