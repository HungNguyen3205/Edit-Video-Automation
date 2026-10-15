"""Real browser -> HTTP -> MP4 smoke check using explicitly synthetic fixtures.

Requires CHROME_PATH and Playwright for Node (PLAYWRIGHT_MODULE may be an
absolute module path). No ASR/model is mocked: reviewed SRT is imported through
the real API; Ollama is intentionally unavailable to exercise labelled fallback.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from editing import probe


def command(args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    args=parser.parse_args()
    out=Path(args.output_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    source=out/'synthetic-source.mp4';music=out/'test-music.wav';photo=out/'synthetic-property.png'
    command(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=360x640:r=30:d=12',
             '-f','lavfi','-i','sine=frequency=440:duration=12','-c:v','libx264','-threads','2',
             '-pix_fmt','yuv420p','-c:a','aac',str(source)])
    command(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:duration=8',str(music)])
    image=Image.new('RGB',(720,1000),'#d8cdbb');draw=ImageDraw.Draw(image)
    draw.rectangle((0,680,720,1000),fill='#587161')
    draw.rectangle((100,210,620,710),fill='#f6f0e6');draw.polygon([(65,220),(360,70),(655,220)],fill='#344b4a')
    for x in (155,425):draw.rectangle((x,300,x+140,470),fill='#658b9b')
    draw.rectangle((300,500,420,710),fill='#526862')
    draw.text((40,920),'SYNTHETIC QA IMAGE - NOT AN ACTUAL PROPERTY',fill='white')
    image.save(photo)
    env={**os.environ,'VIDEO_DATA_DIR':str(out/'data'),'OLLAMA_URL':'http://127.0.0.1:9',
         'PRESET_QA_DIR':str(out)}
    browser_test=r'''
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=process.env.PRESET_QA_DIR, base='http://127.0.0.1:8765';
async function api(url,options={}) {const r=await fetch(base+url,options);const body=await r.json();assert(r.ok,JSON.stringify(body));return body;}
async function upload(id,name,role) {const f=new FormData();f.append('file',new Blob([fs.readFileSync(path.join(root,name))]),name);f.append('role',role);return api(`/api/projects/${id}/upload`,{method:'POST',body:f});}
(async()=>{
  let form=new FormData();form.append('name','Preset browser QA — synthetic source');
  let project=await api('/api/projects',{method:'POST',body:form});
  project=await upload(project.id,'synthetic-source.mp4','main');
  form=new FormData();form.append('file',new Blob(['1\n00:00:00,000 --> 00:00:04,000\nMỗi ngày chúng ta tiến thêm một bước.\n\n2\n00:00:04,000 --> 00:00:08,000\nCăn nhà có khu vườn thoáng mát.\n\n3\n00:00:08,000 --> 00:00:12,000\nGiữ lại những điều có ý nghĩa.\n']),'reviewed.srt');
  project=await api(`/api/projects/${project.id}/subtitles/import`,{method:'POST',body:form});
  const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,args:['--no-sandbox','--disable-gpu']});
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const results=[];
  try {
    await page.goto(base);await page.evaluate(id=>localStorage.setItem('danava-last-video',id),project.id);await page.reload();
    await page.waitForFunction(()=>document.querySelector('#file-title').textContent==='synthetic-source.mp4');
    assert.equal(await page.locator('.preset-card').count(),3);
    for(const style of ['inspirational','real_estate']) {
      await page.locator(`input[name="style-preset"][value="${style}"]`).check();
      assert(await page.locator('#motion-style').isDisabled());
      if(style==='inspirational') {
        await page.locator('#images-input').setInputFiles(path.join(root,'synthetic-property.png'));
        await page.locator('#image-selections input').fill('');
        await page.locator('#music-input').setInputFiles(path.join(root,'test-music.wav'));
      }
      await page.locator('#create-video').click();
      await page.waitForFunction(()=>document.querySelector('input[name="style-preset"]').disabled);
      await page.waitForFunction(()=>!document.querySelector('#download-video').hidden || !document.querySelector('#error-box').hidden,{},{timeout:180000});
      assert(await page.locator('#error-box').isHidden(),await page.locator('#error-detail').textContent());
      project=await api(`/api/projects/${project.id}`);
      assert.equal(project.job.status,'succeeded');assert.equal(project.job.planning_mode,'fallback');
      assert.equal(project.edit_plan.style_preset.id,style);
      assert.equal(project.edit_plan.audio_tracks.filter(x=>x.kind==='music').length,1);
      assert.equal(project.edit_plan.subtitles.map(s=>s.text).join(' '),'Mỗi ngày chúng ta tiến thêm một bước. Căn nhà có khu vườn thoáng mát. Giữ lại những điều có ý nghĩa.');
      await page.screenshot({path:path.join(root,`${style}-desktop.png`),fullPage:true});
      results.push({style,project_id:project.id,output:project.output_path,planning_mode:project.job.planning_mode,
        font:project.edit_plan.typography.profile_id,scenes:project.edit_plan.storyboard.length,
        photo_scenes:project.edit_plan.director.illustration_count,
        duration_audit:project.duration_audit,timings:project.job.timings});
      await page.reload();await page.waitForFunction(()=>document.querySelector('#result-badge').textContent.startsWith('Hoàn thành'));
      assert(await page.locator(`input[value="${style}"]`).isChecked());
      assert.equal(await page.locator('#music-selection').textContent(),'test-music.wav');
    }
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(root,'mobile.png'),fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.equal(errors.length,0,errors.join('\n'));
    fs.writeFileSync(path.join(root,'browser-report.json'),JSON.stringify({results,page_errors:errors,mobile_overflow:false},null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
'''
    log=(out/'server.log').open('w')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8765'],cwd=ROOT,env=env,stdout=log,stderr=log)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8765/api/style-presets',timeout=1):break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('QA server did not start')
        subprocess.run(['node','-e',browser_test],check=True,env=env,cwd=ROOT)
    finally:
        server.terminate();server.wait(timeout=10);log.close()
    report=json.loads((out/'browser-report.json').read_text())
    import numpy as np
    def tone_amplitude(video,frequency):
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(video),'-t','3','-vn','-f','f32le','-ac','1','-ar','16000','-'],check=True,capture_output=True).stdout
        samples=np.frombuffer(raw,dtype=np.float32)
        times=np.arange(len(samples))/16000
        return float(2*abs(np.sum(samples*np.exp(-2j*np.pi*frequency*times)))/len(samples))
    source_voice=tone_amplitude(source,440);source_music=tone_amplitude(source,220)
    for result in report['results']:
        video=out/'data'/'outputs'/Path(result['output']).name
        meta=probe(video);assert abs(meta['duration']-12)<.05 and meta['has_audio']
        assert (meta['width'],meta['height'])==(720,1280)
        command(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'])
        frame=out/(result['style']+'-frame.png')
        command(['ffmpeg','-v','error','-y','-ss','5','-i',str(video),'-frames:v','1',str(frame)])
        result.update(metadata=meta,full_decode=True)
        music_level=tone_amplitude(video,220);voice_level=tone_amplitude(video,440)
        assert music_level>max(.00005,source_music*3) and voice_level>source_voice*.7
        result['audio_tones']={'source_440hz':source_voice,'output_440hz':voice_level,
            'source_220hz':source_music,'output_220hz':music_level,
            'original_audio_retained':True,'uploaded_music_audible':True}
    assert report['results'][0]['scenes']!=report['results'][1]['scenes']
    from PIL import ImageChops,ImageStat
    delta=ImageStat.Stat(ImageChops.difference(Image.open(out/'inspirational-frame.png'),Image.open(out/'real_estate-frame.png'))).mean
    assert sum(delta)>10
    report.update(fixture='Synthetic test pattern + tones + generated test property image + manually supplied SRT',
        real_asr_tested=False,real_model_inference_tested=False,frame_difference_mean_rgb=delta)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
