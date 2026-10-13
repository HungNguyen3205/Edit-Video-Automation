'use strict';
const $ = id => document.getElementById(id);
let current = null, selected = null, busy = false, localURL = null;
let timer = null, pollBusy = false, generation = 0;
const ongoing = p => ['queued','running'].includes(p?.job?.status);
function visible(id, yes) { $(id).hidden = !yes; }
async function api(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `Không kết nối được với tool (${response.status}).`);
  return body;
}
function json(body) { return {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}; }
function error(message, code = '') {
  visible('error-box',true);
  $('error-detail').textContent = message;
  let note = 'Tool chưa tạo được bản dựng. Video gốc vẫn được giữ. Bạn có thể bấm tạo lại.';
  if (/TIMEOUT/.test(code) || /vượt\s*10\s*phút|quá thời gian|quá nhiều thời gian|timeout|timed out/i.test(message))
    note = 'AI mất quá nhiều thời gian để lập kế hoạch. Tác vụ đã dừng; video gốc vẫn được giữ. Kiểm tra tốc độ model và tài nguyên máy trước khi thử lại.';
  else if (/^AI_(CONNECTION|MODEL_ERROR|STREAM)/.test(code) || /Không gọi được Ollama|Không kết nối/i.test(message))
    note = 'Không nhận được kế hoạch hoàn chỉnh từ AI. Kiểm tra kết nối Ollama và trạng thái model, rồi thử lại.';
  else if (code === 'AI_OUTPUT_LIMIT')
    note = 'AI chưa hoàn tất kế hoạch trong giới hạn sinh kết quả. Chưa xuất video từ kế hoạch bị cụt; xem chi tiết để xử lý.';
  else if (/Chưa có Ollama|Chưa cài Whisper|Không tìm thấy Chrome|Cài FFmpeg|cần Node.js|Chưa cài.*model/i.test(message))
    note = 'Máy chạy tool còn thiếu hoặc chưa chạy một thành phần dựng video. Mở hướng dẫn bên dưới để chuẩn bị, rồi thử lại.';
  else if (/AI chưa|storyboard|bản dựng hợp lệ/i.test(message))
    note = 'AI chưa lập được các cảnh phù hợp. Hãy bấm tạo lại hoặc viết yêu cầu ngắn, rõ hơn.';
  else if (/dung lượng|giới hạn|Hỗ trợ video|file không phải|upload/i.test(message)) note = message;
  $('error-text').textContent = note;
}
function lock(yes) {
  busy = yes;
  $('drop-zone').disabled = yes;
  $('prompt').disabled = yes;
  $('history-toggle').disabled = yes;
  $('create-video').disabled = yes || (!selected && !current?.video);
  $('create-video').querySelector('span').textContent = yes ? 'AI đang dựng video…' : current?.output_path ? 'Dựng lại theo yêu cầu này' : 'Tạo video của tôi';
}
function progress(title, value = null, cancelable = true) {
  visible('render-progress',true); visible('download-video',false); visible('result-note',false);
  $('progress-title').textContent = title;
  $('progress-percent').textContent = Number.isFinite(value) ? `${Math.round(value)}%` : '';
  if (Number.isFinite(value)) $('progress-bar').value = value; else $('progress-bar').removeAttribute('value');
  visible('cancel-render',cancelable);
  $('result-badge').textContent = 'Đang dựng'; $('result-badge').classList.remove('done');
}
function player(path) {
  if ($('player').getAttribute('src') !== path) { $('player').pause(); $('player').src = path; $('player').load(); }
  visible('player',true);visible('empty-player',false);
}
function sourceInfo(video) {
  const meta = video.metadata || {};
  $('meta-name').textContent = video.original_name || 'Video của bạn';
  $('meta-detail').textContent = meta.duration ? `${Number(meta.duration).toFixed(1)} giây` : '';
  visible('file-meta',true);
}
function stopPolling() { clearTimeout(timer);timer = null; }
function beginPolling() { stopPolling();timer = setTimeout(poll,500); }
async function poll() {
  if (!current || pollBusy) return;
  pollBusy = true;
  const id = current.id, token = generation;
  try {
    const p = await api(`/api/projects/${id}`);
    if (generation !== token || current?.id !== id) return;
    current = p;
    const job = p.job;
    if (ongoing(p)) {
      progress(job.phase || 'Đang dựng video',job.progress);
      $('progress-note').textContent = job.planning_mode === 'fallback' ? 'Đang dựng dự phòng từ lời nói gốc. AI chưa hoàn thành kế hoạch.' : 'Bạn không cần thêm hiệu ứng thủ công.';
      timer = setTimeout(poll,1200);
    } else if (job?.status === 'succeeded' && p.output_path && p.output_revision === p.revision) {
      finish(p);
    } else {
      visible('render-progress',false);lock(false);
      $('result-badge').textContent = job?.status === 'cancelled' ? 'Đã dừng' : 'Cần thử lại';
      if (job?.status !== 'cancelled') error(job?.error || 'Chưa có video kết quả. Hãy bấm tạo video để thử lại.',job?.error_code);
    }
  } catch (e) {
    if (generation !== token) return;
    $('progress-note').textContent = 'Đang kết nối lại. Video tiếp tục được dựng trên máy chạy tool.';
    timer = setTimeout(poll,3000);
  } finally { pollBusy = false; }
}
function finish(p) {
  stopPolling();lock(false);visible('render-progress',false);visible('error-box',false);
  player(p.output_path);$('download-video').href = p.output_path;
  $('download-video').download = `${(p.video.original_name || 'video').replace(/\.[^.]+$/,'')}-AI.mp4`;
  visible('download-video',true);visible('result-note',true);
  $('result-badge').textContent = p.job?.planning_mode === 'fallback' ? 'Hoàn thành · Dự phòng' : 'Hoàn thành';$('result-badge').classList.add('done');
  $('meta-name').textContent = 'Video đã dựng';
  $('meta-detail').textContent = `${Number(p.duration_audit?.ffprobe_duration || p.video.metadata.duration).toFixed(1)} giây · MP4`;
  $('warning-list').replaceChildren();
  const warnings = p.job?.warnings || [];
  warnings.forEach(text => { const li = document.createElement('li');li.textContent = text;$('warning-list').append(li); });
  visible('warnings',warnings.length > 0);
}
function choose(file) {
  if (!file || busy) return;
  if (!/\.(mp4|mov|webm|mkv)$/i.test(file.name)) { error('Hỗ trợ video MP4, MOV, WEBM hoặc MKV.');return; }
  generation++;stopPolling();current = null;selected = file;
  if (localURL) URL.revokeObjectURL(localURL);
  localURL = URL.createObjectURL(file);player(localURL);
  $('drop-zone').classList.add('selected');$('file-title').textContent = file.name;
  $('file-note').textContent = `${(file.size/1024/1024).toFixed(1)} MB · Bấm để thay video`;
  $('result-badge').textContent = 'Video gốc';$('result-badge').classList.remove('done');
  $('meta-name').textContent = file.name;$('meta-detail').textContent = '';
  visible('file-meta',true);visible('error-box',false);visible('download-video',false);visible('result-note',false);visible('render-progress',false);
  lock(false);
}
function upload(id,file) {
  return new Promise((resolve,reject) => {
    const request = new XMLHttpRequest();
    request.open('POST',`/api/projects/${id}/upload`);
    request.upload.onprogress = e => { if (e.lengthComputable) progress('Đang gửi video',100*e.loaded/e.total,false); };
    request.onload = () => {
      let data;try { data = JSON.parse(request.responseText); } catch { reject(new Error('Không nhận được phản hồi khi tải video.'));return; }
      request.status >= 200 && request.status < 300 ? resolve(data) : reject(new Error(data.detail || 'Không tải được video.'));
    };
    request.onerror = () => reject(new Error('Mất kết nối khi gửi video. Kiểm tra tool còn đang chạy rồi thử lại.'));
    const body = new FormData();body.append('file',file);body.append('role','main');request.send(body);
  });
}
async function create() {
  if (busy || (!selected && !current?.video)) return;
  const token = generation;lock(true);visible('error-box',false);$('progress-note').textContent = 'Bạn không cần thêm hiệu ứng thủ công.';
  if (innerWidth<=680) $('result-title').scrollIntoView({behavior:'smooth',block:'start'});
  try {
    if (!current?.video) {
      progress('Đang gửi video',null,false);
      if (!current) {
        const form = new FormData();form.append('name',selected.name.replace(/\.[^.]+$/,''));
        current = await api('/api/projects',{method:'POST',body:form});
        localStorage.setItem('danava-last-video',current.id);
      }
      current = await upload(current.id,selected);sourceInfo(current.video);
    }
    if (token !== generation) return;
    progress('AI đang chuẩn bị bản dựng');
    current = await api(`/api/projects/${current.id}/make-video`,json({prompt:$('prompt').value.trim()}));
    localStorage.setItem('danava-last-video',current.id);
    beginPolling();
  } catch (e) {
    if (token !== generation) return;
    visible('render-progress',false);$('result-badge').textContent = 'Cần thử lại';lock(false);error(e.message);
  }
}
async function openProject(id) {
  if (busy) return;
  const token=++generation;
  try {
    const p = await api(`/api/projects/${id}`);
    if (!p.video || generation!==token || busy) return;
    stopPolling();current = p;selected = null;
    $('prompt').value = p.edit_plan?.director?.user_prompt ?? p.edit_plan?.director?.prompt ?? '';
    $('file-title').textContent = p.video.original_name;$('file-note').textContent = 'Bấm để thay video';$('drop-zone').classList.add('selected');
    visible('error-box',false);sourceInfo(p.video);player(`/assets/${p.video.filename}`);
    visible('history-panel',false);localStorage.setItem('danava-last-video',id);
    if (ongoing(p)) { lock(true);beginPolling(); }
    else if (p.output_path && p.output_revision === p.revision && p.job?.status!=='failed') finish(p);
    else { lock(false);visible('download-video',false);visible('result-note',false);$('result-badge').textContent = 'Video gốc';if(p.job?.status === 'failed')error(p.job.error,p.job.error_code); }
  } catch(e) { error(e.message); }
}
$('drop-zone').onclick = () => $('video-input').click();
$('video-input').onchange = () => { choose($('video-input').files[0]);$('video-input').value = ''; };
['dragenter','dragover'].forEach(name => $('drop-zone').addEventListener(name,e => { e.preventDefault();if(!busy)$('drop-zone').classList.add('dragging'); }));
['dragleave','drop'].forEach(name => $('drop-zone').addEventListener(name,e => { e.preventDefault();$('drop-zone').classList.remove('dragging');if(name === 'drop')choose(e.dataTransfer.files[0]); }));
window.addEventListener('dragover',e => e.preventDefault());window.addEventListener('drop',e => e.preventDefault());
$('create-video').onclick = create;
$('cancel-render').onclick = async () => { if(!current)return;$('cancel-render').disabled = true;try{await api(`/api/projects/${current.id}/cancel`,json({}));$('progress-note').textContent = 'Đang dừng tác vụ…';}catch(e){error(e.message);}finally{$('cancel-render').disabled = false;} };
$('history-close').onclick = () => visible('history-panel',false);
$('history-toggle').onclick = async () => {
  if (busy) return;
  visible('history-panel',!$('history-panel').hidden);if($('history-panel').hidden)return;
  try {
    const list = await api('/api/projects');$('history-list').replaceChildren();
    const videos = list.filter(p=>p.video);
    if (!videos.length) $('history-list').textContent = 'Chưa có video. Thả video đầu tiên để bắt đầu.';
    videos.slice(0,20).forEach(p => { const button = document.createElement('button');button.className = 'history-item';
      const name = document.createElement('strong');name.textContent = p.video.original_name || p.name;
      const state = document.createElement('span');state.textContent = p.export_status === 'succeeded' ? 'Đã dựng' : 'Video gốc';button.append(name,state);button.onclick = () => openProject(p.id);$('history-list').append(button);
    });
  } catch(e) { error(e.message); }
};
async function initialize() {
  try {
    const health = await api('/api/health');
    const ready = health.ffmpeg && health.ffprobe && health.motion?.ready && health.whisper;
    $('service-status').classList.toggle('ready',ready);$('service-status').lastChild.textContent = ready ? 'Sẵn sàng dựng' : 'Cần chuẩn bị máy';
  } catch { $('service-status').lastChild.textContent = 'Chưa kết nối tool'; }
  const last = localStorage.getItem('danava-last-video');if(last&&!selected&&!busy)await openProject(last);
}
initialize();
