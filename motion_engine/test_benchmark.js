const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');
const path = require('path');

async function testBenchmark() {
  const t0 = Date.now();
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 720, height: 1280, deviceScaleFactor: 1 });
  await page.setContent(`
    <!DOCTYPE html>
    <html><body style="margin:0;background:#ffffff;display:flex;align-items:center;justify-content:center;height:1280px;width:720px;">
      <h1 id="title" style="font-family:sans-serif;font-size:40px;color:#0D9488;">Frame 0</h1>
    </body></html>
  `);

  const fps = 30;
  const duration = 2; // 2 seconds = 60 frames
  const totalFrames = fps * duration;

  const ffmpeg = spawn('ffmpeg', [
    '-y',
    '-f', 'image2pipe',
    '-vcodec', 'png',
    '-r', fps.toString(),
    '-i', '-',
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-preset', 'ultrafast',
    'test_motion.mp4'
  ]);

  for (let f = 0; f < totalFrames; f++) {
    await page.evaluate((frame) => {
      document.getElementById('title').innerText = 'Frame ' + frame;
    }, f);
    const buffer = await page.screenshot({ type: 'png' });
    ffmpeg.stdin.write(buffer);
  }
  ffmpeg.stdin.end();

  await new Promise((resolve) => ffmpeg.on('close', resolve));
  await browser.close();
  console.log(`Rendered ${totalFrames} frames in ${((Date.now() - t0) / 1000).toFixed(2)}s`);
}

testBenchmark();
