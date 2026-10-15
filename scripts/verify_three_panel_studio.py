"""Real three-panel UI -> single source -> chosen preset -> decoded MP4.

Fixtures are synthetic. Reviewed SRT is supplied through the real API, not ASR;
Ollama is deliberately unavailable and the output must be labelled fallback.
Requires CHROME_PATH, Node and Playwright (or PLAYWRIGHT_MODULE).
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from editing import probe


def command(args):
    return subprocess.run(args,check=True,capture_output=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',required=True);args=parser.parse_args()
    out=Path(args.output_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    source=out/'synthetic-source.mp4';silent=out/'silent-source.mp4'
    command(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=360x640:r=30:d=12',
        '-f','lavfi','-i','sine=frequency=440:duration=12','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',str(source)])
    command(['ffmpeg','-v','error','-y','-i',str(source),'-t','4','-an','-c:v','copy',str(silent)])
    env={**os.environ,'VIDEO_DATA_DIR':str(out/'data'),'OLLAMA_URL':'http://127.0.0.1:9','STUDIO_QA_DIR':str(out)}
    js=r'''
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=process.env.STUDIO_QA_DIR,base='http://127.0.0.1:8765';
async function api(url,options={}){const r=await fetch(base+url,options),p=await r.json();assert(r.ok,JSON.stringify(p));return p;}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH,args:['--no-sandbox','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],results=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(base);await page.waitForSelector('input[name="style"]');
  assert.equal(await page.locator('main section[data-panel]').count(),3);
  assert.equal(await page.locator('textarea,select').count(),0);
  assert(await page.locator('#render').isDisabled());
  // Full real upload through the product; silent fixture needs no recognizer.
  await page.locator('#video-input').setInputFiles(path.join(root,'silent-source.mp4'));
  await page.locator('input[name="style"][value="inspirational"]').check();
  await page.locator('#render').click();
  await page.waitForFunction(()=>!document.querySelector('#download').hidden||!document.querySelector('#error').hidden,{},{timeout:180000});
  assert(await page.locator('#error').isHidden(),await page.locator('#error').textContent());
  const uploadId=await page.evaluate(()=>localStorage.getItem('danava-last-video'));
  const uploaded=await api(`/api/projects/${uploadId}`);assert.equal(uploaded.job.status,'succeeded');assert.equal(uploaded.edit_plan.style_preset.id,'inspirational');
  // Audio fixture uses explicitly supplied SRT, not a mocked or claimed ASR run.
  let form=new FormData();form.append('name','Three-panel QA - synthetic');
  let p=await api('/api/projects',{method:'POST',body:form});
  form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(root,'synthetic-source.mp4'))]),'synthetic-source.mp4');form.append('role','main');
  p=await api(`/api/projects/${p.id}/upload`,{method:'POST',body:form});
  form=new FormData();form.append('file',new Blob(['1\n00:00:00,000 --> 00:00:04,000\nMỗi ngày chúng ta tiến thêm một bước.\n\n2\n00:00:04,000 --> 00:00:08,000\nCăn nhà có khu vườn thoáng mát.\n\n3\n00:00:08,000 --> 00:00:12,000\nGiữ lại những điều có ý nghĩa.\n']),'reviewed.srt');
  p=await api(`/api/projects/${p.id}/subtitles/import`,{method:'POST',body:form});
  await page.evaluate(id=>localStorage.setItem('danava-last-video',id),p.id);await page.reload();
  await page.waitForFunction(()=>document.querySelector('#file-title').textContent==='synthetic-source.mp4');
  for(const style of ['explainer','inspirational','real_estate']){
   await page.locator(`input[name="style"][value="${style}"]`).check();
   assert(await page.locator('#download').isHidden());
   await page.locator('#render').click();await page.waitForFunction(()=>document.querySelector('#render').disabled);
   await page.waitForFunction(()=>!document.querySelector('#download').hidden||!document.querySelector('#error').hidden,{},{timeout:180000});
   assert(await page.locator('#error').isHidden(),await page.locator('#error').textContent());
   p=await api(`/api/projects/${p.id}`);
   assert.equal(p.job.status,'succeeded');assert.equal(p.job.planning_mode,'fallback');assert.equal(p.edit_plan.style_preset.id,style);
   assert.equal(p.edit_plan.assets.length,1);assert(p.edit_plan.style_preset.caption_design);
   assert.equal(p.edit_plan.subtitles.map(s=>s.text).join(' '),'Mỗi ngày chúng ta tiến thêm một bước. Căn nhà có khu vườn thoáng mát. Giữ lại những điều có ý nghĩa.');
   if(style!=='explainer'){assert(p.edit_plan.storyboard.some(s=>s.source_cutaway));assert(p.edit_plan.effect_keyframes.some(e=>e.direction==='in'));assert(p.edit_plan.effect_keyframes.some(e=>e.direction==='out'));}
   await page.screenshot({path:path.join(root,`${style}-desktop.png`),fullPage:true});
   results.push({style,output:p.output_path,planning_mode:p.job.planning_mode,font:p.edit_plan.typography.profile_id,
    scenes:p.edit_plan.storyboard.length,source_frame_count:p.edit_plan.style_preset.source_frame_count||0,
    zoom_directions:p.edit_plan.effect_keyframes.map(e=>e.direction||'breath'),duration_audit:p.duration_audit,timings:p.job.timings});
   await page.reload();await page.waitForSelector('#download:not([hidden])');assert(await page.locator(`input[name="style"][value="${style}"]`).isChecked());
  }
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(250);
  const boxes=await page.locator('main section[data-panel]').evaluateAll(nodes=>nodes.map(n=>({top:n.getBoundingClientRect().top+scrollY,bottom:n.getBoundingClientRect().bottom+scrollY,width:n.getBoundingClientRect().width})));
  assert(boxes.every(b=>b.width<=390));assert(boxes[1].top-boxes[0].bottom<25&&boxes[2].top-boxes[1].bottom<25);
  await page.locator('[data-panel="style"]').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'mobile-style.png')});
  await page.locator('[data-panel="output"]').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(root,'mobile-result.png')});
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(root,'mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.equal(errors.length,0,errors.join('\n'));
  fs.writeFileSync(path.join(root,'browser-report.json'),JSON.stringify({results,page_errors:errors,mobile_overflow:false,panels:3,extra_form_controls:0,silent_upload_via_ui:true,single_source_only:true},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
'''
    with (out/'server.log').open('w') as log:
        server=subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8765'],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8765/api/style-presets',timeout=1):break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('QA server did not start')
            subprocess.run(['node','-e',js],env=env,cwd=ROOT,check=True)
        finally:server.terminate();server.wait(timeout=10)
    report=json.loads((out/'browser-report.json').read_text())
    import numpy as np
    from PIL import Image,ImageChops,ImageStat
    for result in report['results']:
        video=out/'data'/'outputs'/Path(result['output']).name
        meta=probe(video);assert abs(meta['duration']-12)<.05 and meta['has_audio']
        assert (meta['width'],meta['height'])==(720,1280)
        command(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'])
        frame=out/(result['style']+'-frame.png')
        command(['ffmpeg','-v','error','-y','-ss','1.6','-i',str(video),'-frames:v','1',str(frame)])
        pixels=np.asarray(Image.open(frame).convert('RGB'))
        lower=pixels[1000:1200].astype(float)
        colored=(lower[:,:,0]>180)&(lower[:,:,1]>110)&(lower[:,:,2]<lower[:,:,1]*.83)&(lower[:,:,0]>lower[:,:,1]*1.04)
        assert int(colored.sum())>50,('Missing colored captions',result['style'])
        result.update(metadata=meta,full_decode=True,colored_caption_pixels=int(colored.sum()))
        raw=command(['ffmpeg','-v','error','-i',str(video),'-t','3','-vn','-f','f32le','-ac','1','-ar','16000','-']).stdout
        samples=np.frombuffer(raw,dtype=np.float32);times=np.arange(len(samples))/16000
        amplitude=float(2*abs(np.sum(samples*np.exp(-2j*np.pi*440*times)))/len(samples));assert amplitude>.08
        result['original_audio_tone_amplitude']=amplitude
    delta=ImageStat.Stat(ImageChops.difference(Image.open(out/'inspirational-frame.png'),Image.open(out/'real_estate-frame.png'))).mean
    assert sum(delta)>10
    report.update(fixture='Synthetic source with tone; manually supplied SRT; no uploaded images or music',real_asr_tested=False,
        real_model_inference_tested=False,frame_difference_mean_rgb=delta)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
