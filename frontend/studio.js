'use strict';
const $ = id => document.getElementById(id);
let project = null, file = null, busy = false, style = '', catalog = [], timer = null, objectURL = null, epoch = 0, polling = false;
let selectedLogoId = '', selectedMusicId = '', selectedImageIds = new Set(), selectedBrollIds = new Set();

const active = p => ['queued', 'running'].includes(p?.job?.status);
const visible = (id, on) => { const el = $(id); if (el) el.hidden = !on; };
const selectedLabel = () => catalog.find(p => p.id === style)?.label || style;

async function api(path, options = {}) {
  const r = await fetch(path, options);
  const b = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(typeof b.detail === 'string' ? b.detail : `Không kết nối được tool (${r.status}).`);
  return b;
}
const json = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

function updateExtraBadge() {
  const parts = [];
  if (selectedLogoId) parts.push('1 logo');
  if (selectedMusicId) parts.push('1 nhạc nền');
  if (selectedImageIds.size) parts.push(`${selectedImageIds.size} ảnh`);
  if (selectedBrollIds.size) parts.push(`${selectedBrollIds.size} B-roll`);
  const badge = $('extra-badge');
  if (badge) badge.textContent = parts.length > 0 ? `Đã chọn: ${parts.join(', ')}` : 'Mặc định tự động';
  const countBadge = $('sub-assets-count');
  if (countBadge) countBadge.textContent = `${selectedImageIds.size}/6 ảnh · ${selectedBrollIds.size}/6 B-roll`;
}

function renderExtraAssets() {
  const assets = project?.edit_plan?.assets || [];
  const mainVidId = project?.video?.asset_id;

  // 1. Logo
  const logoBox = $('logo-box');
  const btnUploadLogo = $('btn-upload-logo');
  const logoAsset = assets.find(a => a.id === selectedLogoId) || assets.find(a => a.usage === 'logo');
  if (selectedLogoId && logoAsset) {
    selectedLogoId = logoAsset.id;
    logoBox.innerHTML = `<span>🏷 ${logoAsset.original_name}</span><button type="button" class="btn-remove-tag" id="btn-del-logo" title="Bỏ chọn logo">✕</button>`;
    visible('logo-box', true);
    visible('btn-upload-logo', false);
    $('btn-del-logo').onclick = () => { selectedLogoId = ''; renderExtraAssets(); };
  } else {
    selectedLogoId = '';
    visible('logo-box', false);
    visible('btn-upload-logo', true);
  }

  // 2. Music
  const musicBox = $('music-box');
  const btnUploadMusic = $('btn-upload-music');
  const musicAsset = assets.find(a => a.id === selectedMusicId) || assets.find(a => a.type === 'audio');
  if (selectedMusicId && musicAsset) {
    selectedMusicId = musicAsset.id;
    musicBox.innerHTML = `<span>🎵 ${musicAsset.original_name}</span><button type="button" class="btn-remove-tag" id="btn-del-music" title="Bỏ chọn nhạc">✕</button>`;
    visible('music-box', true);
    visible('btn-upload-music', false);
    $('btn-del-music').onclick = () => { selectedMusicId = ''; renderExtraAssets(); };
  } else {
    selectedMusicId = '';
    visible('music-box', false);
    visible('btn-upload-music', true);
  }

  // 3. Sub-assets list (Images and B-roll)
  const container = $('assets-container');
  if (!container) return;
  const candidateAssets = assets.filter(a => a.id !== mainVidId && a.id !== selectedLogoId && a.type !== 'audio');

  if (candidateAssets.length === 0) {
    container.innerHTML = '<p class="empty-assets-note">Chưa tải tài nguyên phụ nào. Bạn có thể bấm nút trên để thêm ảnh hoặc video B-roll.</p>';
  } else {
    container.innerHTML = '';
    candidateAssets.forEach(a => {
      const isVideo = a.type === 'video';
      const isChecked = isVideo ? selectedBrollIds.has(a.id) : selectedImageIds.has(a.id);
      const label = document.createElement('label');
      label.className = 'asset-check-item';
      label.innerHTML = `
        <input type="checkbox" data-id="${a.id}" data-type="${a.type}" ${isChecked ? 'checked' : ''} ${busy ? 'disabled' : ''}>
        <span class="asset-badge-type ${isVideo ? 'badge-video' : 'badge-image'}">${isVideo ? 'B-roll' : 'Ảnh'}</span>
        <span class="asset-info-name" title="${a.original_name}">${a.original_name}</span>
        <span class="asset-info-meta">${isVideo ? `${Number(a.metadata?.duration || 0).toFixed(1)}s` : `${a.metadata?.width || ''}×${a.metadata?.height || ''}`}</span>
      `;
      const input = label.querySelector('input');
      input.onchange = () => {
        if (input.checked) {
          if (isVideo) {
            if (selectedBrollIds.size >= 6) { input.checked = false; alert('Tối đa 6 video B-roll.'); return; }
            selectedBrollIds.add(a.id);
          } else {
            if (selectedImageIds.size >= 6) { input.checked = false; alert('Tối đa 6 ảnh minh họa.'); return; }
            selectedImageIds.add(a.id);
          }
        } else {
          if (isVideo) selectedBrollIds.delete(a.id);
          else selectedImageIds.delete(a.id);
        }
        updateExtraBadge();
      };
      container.appendChild(label);
    });
  }
  updateExtraBadge();
}

function controls(on) {
  busy = on;
  $('drop-zone').disabled = on;
  $('video-input').disabled = on;
  document.querySelectorAll('input[name="style"]').forEach(el => el.disabled = on);
  $('render').disabled = on || !style || (!file && !project?.video);
  $('render').textContent = on ? 'Đang dựng video…' : 'Dựng & xuất video';

  // Lock optional controls during active render to prevent revision drift
  for (const id of ['input-prompt', 'input-brand-name', 'input-proper-names', 'input-web-url', 'btn-fetch-web', 'chk-illustrations', 'chk-remove-fillers', 'btn-upload-logo', 'btn-upload-music', 'btn-upload-image', 'btn-upload-broll']) {
    const el = $(id);
    if (el) el.disabled = on;
  }
  document.querySelectorAll('#assets-container input[type="checkbox"]').forEach(el => el.disabled = on);
}

function clearResult() {
  for (const id of ['result-player', 'download', 'result-status', 'status-badge', 'render-report', 'warnings', 'error']) visible(id, false);
  $('result-player').pause();
  visible('empty-result', true);
}

function source(p) {
  $('file-title').textContent = p.video.original_name;
  $('file-note').textContent = 'Bấm để thay video';
  $('source-player').src = `/assets/${p.video.filename}`;
  visible('source-player', true);
  $('source-meta').textContent = `${Number(p.video.metadata.duration).toFixed(1)} giây · Video gốc được giữ riêng.`;
}

function showStyle() {
  const preset = catalog.find(p => p.id === style);
  $('style-note').textContent = preset ? (
    preset.id === 'real_estate' ? 'Chữ trắng–gold, thẻ thông tin, zoom in/out nhẹ. Hình bổ sung lấy từ video gốc hoặc B-roll.' :
    preset.id === 'inspirational' ? 'Chữ nhấn màu vàng–cam, phụ đề động và zoom in/out theo nhịp kể chuyện.' :
    'Chữ nhấn nổi bật, bố cục giải thích và chuyển động năng động.'
  ) : 'Chọn một phong cách để bắt đầu.';
  if (!busy) controls(false);
}

function fail(message) {
  visible('progress', false);
  controls(false);
  visible('error', true);
  $('error').textContent = message;
  $('render-hint').textContent = 'Chưa có bản dựng mới. Video gốc vẫn được giữ; bạn có thể thử lại.';
  const badge = $('status-badge');
  if (badge) {
    badge.className = 'status-badge status-failed';
    badge.textContent = '✕ Dựng thất bại';
    visible('status-badge', true);
  }
}

function progress(p) {
  visible('progress', true);
  visible('empty-result', false);
  $('phase').textContent = p?.job?.phase || 'Đang gửi video và chuẩn bị bản dựng…';
  const n = p?.job?.progress;
  if (Number.isFinite(n)) $('progress-bar').value = n;
  else $('progress-bar').removeAttribute('value');
  visible('cancel', Boolean(p && active(p)));
}

function finish(p) {
  visible('progress', false);
  controls(false);
  const outputStyle = p.edit_plan?.style_preset?.id || 'explainer';
  if (outputStyle !== style) {
    clearResult();
    fail('Bản dựng chưa khớp phong cách đã chọn. Hãy bấm dựng lại; chưa hiển thị file khác phong cách.');
    return;
  }
  if ((p.edit_plan?.style_preset?.version || 0) < 3) {
    clearResult();
    $('render-hint').textContent = 'Đây là bản dựng cũ. Bấm dựng lại để áp dụng kiểu chữ và chuyển động mới.';
    return;
  }
  visible('empty-result', false);
  $('result-player').src = p.output_path;
  visible('result-player', true);
  $('download').href = p.output_path;
  $('download').download = `${(p.video.original_name || 'video').replace(/\.[^.]+$/, '')}-${style}.mp4`;
  visible('download', true);

  const report = p.render_report || p.job?.render_report || {};
  const statusCode = report.status_code || (p.job?.planning_mode === 'fallback' ? 'fallback' : 'ai_completed');
  const statusLabel = report.status_category || (statusCode === 'fallback' ? 'Bản dự phòng' : 'AI hoàn thành');

  const badge = $('status-badge');
  if (badge) {
    badge.className = `status-badge status-${statusCode}`;
    const icon = statusCode === 'ai_completed' ? '✓' : (statusCode === 'fallback' ? '⚠' : (statusCode === 'needs_review' ? '🔍' : '✕'));
    const reasonTxt = (statusCode === 'fallback' && report.fallback_reason) ? ` (${report.fallback_reason})` : '';
    badge.textContent = `${icon} ${statusLabel}${reasonTxt}`;
    visible('status-badge', true);
  }

  const dur = Number(p.duration_audit?.ffprobe_duration || p.video.metadata.duration).toFixed(1);
  const engineDesc = report.planning_mode === 'fallback' ? 'Dựng dự phòng' : (report.vision_analysis?.vision_used ? 'AI Vision' : 'AI');
  $('result-status').textContent = `${p.edit_plan?.style_preset?.label || selectedLabel()} · ${dur}s · MP4 720×1280 · ${engineDesc}`;
  visible('result-status', true);
  $('render-hint').textContent = 'Đã xuất bản dựng. Xem lại rồi tải video bên dưới.';

  // Render Post-render audit report details
  const reportDetails = $('report-details');
  if (reportDetails && report.plan_metrics) {
    const pm = report.plan_metrics;
    const rm = report.rendered_metrics || {};
    const qg = report.quality_gate || {};
    const va = report.vision_analysis || {};

    reportDetails.innerHTML = `
      <div class="report-grid">
        <div class="report-card">
          <h4>Kế hoạch dự kiến</h4>
          <div class="report-item"><span>Tổng số cảnh:</span><span>${pm.scene_count}</span></div>
          <div class="report-item"><span>Cảnh minh họa:</span><span>${pm.illustration_scene_count} (${pm.illustration_duration_seconds}s)</span></div>
          <div class="report-item"><span>Tỷ lệ minh họa:</span><span>${Math.round((pm.illustration_duration_ratio || 0) * 100)}%</span></div>
          <div class="report-item"><span>Hiệu ứng zoom:</span><span>${pm.zoom_count}</span></div>
          <div class="report-item"><span>Âm thanh SFX:</span><span>${pm.sfx_count}</span></div>
          <div class="report-item"><span>Tài nguyên người dùng:</span><span>${pm.user_assets_used_count} file</span></div>
          <div class="report-item"><span>Phụ đề nhận dạng:</span><span>${pm.subtitle_count} câu</span></div>
        </div>
        <div class="report-card">
          <h4>Xác thực thực tế (Renderer)</h4>
          <div class="report-item"><span>Thời lượng đo được:</span><span>${rm.duration_seconds || dur}s</span></div>
          <div class="report-item"><span>Kích thước khung hình:</span><span>${rm.width || 720} × ${rm.height || 1280}</span></div>
          <div class="report-item"><span>Dung lượng xuất:</span><span>${(Number(rm.file_size_bytes || 0) / 1024 / 1024).toFixed(1)} MB</span></div>
          <div class="report-item"><span>Âm thanh đầu ra:</span><span>${rm.has_audio ? 'Hợp lệ' : 'Thiếu'}</span></div>
          <div class="report-item"><span>Lớp phủ đồ họa:</span><span>${rm.actual_rendered_overlays || 0}</span></div>
          <div class="report-item"><span>Engine thực tế:</span><span>${report.engine || 'rules'} ${report.model ? `(${report.model})` : ''}</span></div>
          <div class="report-item"><span>Thị giác (Vision):</span><span>${va.vision_used ? `Đã quét ${va.sampled_frame_count} frame` : 'Tắt'}</span></div>
        </div>
      </div>
      ${report.fallback_reason_detail ? `
        <div style="margin-top:10px;padding:8px 10px;background:#fef7e0;border:1px solid #feefc3;border-radius:6px;font-size:11px;color:#854d0e">
          <strong>Lý do AI chuyển sang dự phòng:</strong> ${report.fallback_reason_detail}
        </div>
      ` : ''}
      ${qg.low_edit_warning ? `
        <div style="margin-top:8px;padding:8px 10px;background:#fff7ed;border:1px solid #ffedd5;border-radius:6px;font-size:11px;color:#9a3412">
          <strong>Lưu ý mức edit:</strong> ${qg.low_edit_reason}
        </div>
      ` : ''}
    `;
    visible('render-report', true);
  }

  $('warning-list').replaceChildren();
  const warnings = [...new Set(p.job?.warnings || [])];
  for (const text of warnings) {
    const li = document.createElement('li');
    li.textContent = text.replace('Mở mục sửa phụ đề để kiểm tra trước khi dùng video.', 'Hãy nghe và kiểm tra chữ trước khi đăng.');
    $('warning-list').append(li);
  }
  visible('warnings', warnings.length > 0);
}

async function poll() {
  if (polling || !project) return;
  polling = true;
  const id = project.id, token = epoch;
  try {
    const p = await api(`/api/projects/${id}`);
    if (token !== epoch) return;
    project = p;
    if (active(p)) {
      progress(p);
      timer = setTimeout(poll, 1000);
    } else if (p.job?.status === 'succeeded' && p.output_path && p.output_revision === p.revision) {
      finish(p);
    } else if (p.job?.status === 'cancelled') {
      visible('progress', false);
      controls(false);
      visible('empty-result', true);
      $('render-hint').textContent = 'Đã dừng dựng. Bạn có thể chọn phong cách và thử lại.';
    } else {
      fail(p.job?.error || 'Chưa xuất được video. Hãy thử lại.');
    }
  } catch (e) {
    if (token === epoch) {
      $('phase').textContent = 'Đang kết nối lại với máy dựng…';
      timer = setTimeout(poll, 2000);
    }
  } finally {
    polling = false;
  }
}

async function ensureProject() {
  if (!project) {
    const form = new FormData();
    form.append('name', file ? file.name.replace(/\.[^.]+$/, '') : 'Dự án mới');
    project = await api('/api/projects', { method: 'POST', body: form });
  }
  return project;
}

function choose(next) {
  if (!next || busy) return;
  if (!/\.(mp4|mov|webm|mkv)$/i.test(next.name)) {
    fail('Chọn video MP4, MOV, WEBM hoặc MKV.');
    return;
  }
  epoch++;
  clearTimeout(timer);
  project = null;
  file = next;
  localStorage.removeItem('danava-last-video');

  // Reset resource selection for new video/project
  selectedLogoId = '';
  selectedMusicId = '';
  selectedImageIds.clear();
  selectedBrollIds.clear();
  if ($('input-prompt')) $('input-prompt').value = '';
  if ($('input-brand-name')) $('input-brand-name').value = '';
  if ($('input-proper-names')) $('input-proper-names').value = '';
  renderExtraAssets();

  if (objectURL) URL.revokeObjectURL(objectURL);
  objectURL = URL.createObjectURL(next);
  $('source-player').src = objectURL;
  visible('source-player', true);
  $('file-title').textContent = next.name;
  $('file-note').textContent = 'Bấm để thay video';
  $('source-meta').textContent = `${(next.size / 1024 / 1024).toFixed(1)} MB · Video gốc`;
  clearResult();
  $('render-hint').textContent = 'Chọn phong cách rồi bấm dựng. Các hiệu ứng được áp dụng tự động.';
  showStyle();
}

async function uploadSubAsset(subFile, role) {
  if (busy || !subFile) return;
  if (subFile.size > 500 * 1024 * 1024) {
    alert(`Tệp ${subFile.name} vượt quá giới hạn 500MB.`);
    return;
  }
  try {
    $('phase').textContent = `Đang tải ${subFile.name}…`;
    await ensureProject();
    const media = new FormData();
    media.append('file', subFile);
    media.append('role', role);
    const updated = await api(`/api/projects/${project.id}/upload`, { method: 'POST', body: media });
    project = updated;
    const newAsset = project.edit_plan.assets[project.edit_plan.assets.length - 1];
    if (role === 'logo') {
      selectedLogoId = newAsset.id;
    } else if (newAsset.type === 'audio') {
      selectedMusicId = newAsset.id;
    } else if (role === 'broll' || newAsset.type === 'video') {
      selectedBrollIds.add(newAsset.id);
    } else {
      selectedImageIds.add(newAsset.id);
    }
    renderExtraAssets();
  } catch (err) {
    alert(`Không tải được tệp: ${err.message}`);
  }
}

async function render() {
  if (busy || !style || (!file && !project?.video)) return;
  controls(true);
  clearResult();
  progress(project);
  const token = epoch;
  try {
    if (!project?.video) {
      await ensureProject();
      const media = new FormData();
      media.append('file', file);
      media.append('role', 'main');
      project = await api(`/api/projects/${project.id}/upload`, { method: 'POST', body: media });
      source(project);
    }
    if (token !== epoch) return;

    const payload = {
      style_preset: style,
      motion_style: 'dynamic_explainer',
      font_style: 'auto',
      illustrations: $('chk-illustrations')?.checked ?? true,
      remove_fillers: $('chk-remove-fillers')?.checked ?? false,
      prompt: $('input-prompt')?.value.trim() || '',
      brand_name: $('input-brand-name')?.value.trim() || '',
      proper_names: $('input-proper-names')?.value.trim() || '',
      logo_asset_id: selectedLogoId || '',
      music_asset_id: selectedMusicId || '',
      image_asset_ids: Array.from(selectedImageIds).slice(0, 6),
      broll_asset_ids: Array.from(selectedBrollIds).slice(0, 6),
      web_url: $('input-web-url')?.value.trim() || ''
    };

    project = await api(`/api/projects/${project.id}/make-video`, json(payload));
    localStorage.setItem('danava-last-video', project.id);
    progress(project);
    timer = setTimeout(poll, 300);
  } catch (e) {
    if (token === epoch) fail(e.message);
  }
}

// Bind primary controls
$('drop-zone').onclick = () => $('video-input').click();
$('video-input').onchange = () => { choose($('video-input').files[0]); $('video-input').value = ''; };
for (const event of ['dragenter', 'dragover']) {
  $('drop-zone').addEventListener(event, e => { e.preventDefault(); if (!busy) $('drop-zone').classList.add('drag'); });
}
for (const event of ['dragleave', 'drop']) {
  $('drop-zone').addEventListener(event, e => {
    e.preventDefault();
    $('drop-zone').classList.remove('drag');
    if (event === 'drop') choose(e.dataTransfer.files[0]);
  });
}
$('render').onclick = render;
$('cancel').onclick = async () => {
  if (!project) return;
  $('cancel').disabled = true;
  try {
    await api(`/api/projects/${project.id}/cancel`, json({}));
    $('phase').textContent = 'Đang dừng dựng…';
  } catch (e) {
    $('phase').textContent = e.message;
  } finally {
    $('cancel').disabled = false;
  }
};

// Bind sub-asset upload buttons
$('btn-upload-logo').onclick = () => $('logo-input').click();
$('logo-input').onchange = () => { if ($('logo-input').files[0]) uploadSubAsset($('logo-input').files[0], 'logo'); $('logo-input').value = ''; };

$('btn-upload-music').onclick = () => $('music-input').click();
$('music-input').onchange = () => { if ($('music-input').files[0]) uploadSubAsset($('music-input').files[0], 'asset'); $('music-input').value = ''; };

$('btn-upload-image').onclick = () => $('image-input').click();
$('image-input').onchange = () => {
  Array.from($('image-input').files).forEach(f => uploadSubAsset(f, 'asset'));
  $('image-input').value = '';
};

$('btn-upload-broll').onclick = () => $('broll-input').click();
$('broll-input').onchange = () => {
  Array.from($('broll-input').files).forEach(f => uploadSubAsset(f, 'broll'));
  $('broll-input').value = '';
};

const btnFetchWeb = $('btn-fetch-web');
if (btnFetchWeb) {
  btnFetchWeb.onclick = async () => {
    const url = $('input-web-url')?.value.trim();
    if (!url) {
      alert('Vui lòng dán link trang web cần lấy ảnh.');
      return;
    }
    const statusEl = $('web-fetch-status');
    try {
      btnFetchWeb.disabled = true;
      btnFetchWeb.textContent = 'Đang cào…';
      if (statusEl) {
        statusEl.textContent = 'Đang đọc nội dung web và lọc ảnh nét…';
        statusEl.style.color = '#5a7b70';
      }
      await ensureProject();
      const res = await api(`/api/projects/${project.id}/ingest-web`, json({ url, max_images: 5 }));
      project = await api(`/api/projects/${project.id}`);
      for (const a of (res.assets || [])) {
        selectedImageIds.add(a.id);
      }
      renderExtraAssets();
      if (statusEl) {
        statusEl.textContent = `✓ Đã lấy được ${res.image_count} ảnh minh họa: "${(res.title || '').slice(0, 40)}…"`;
        statusEl.style.color = '#10b981';
      }
      if ($('input-prompt') && !$('input-prompt').value.trim() && res.summary) {
        $('input-prompt').value = res.summary;
      }
    } catch (err) {
      if (statusEl) {
        statusEl.textContent = `✕ Lỗi: ${err.message}`;
        statusEl.style.color = '#ef4444';
      }
    } finally {
      btnFetchWeb.disabled = false;
      btnFetchWeb.textContent = 'Lấy ảnh';
    }
  };
}

async function initialize() {
  try {
    const data = await api('/api/style-presets');
    catalog = data.presets;
    $('style-options').replaceChildren();
    const legend = document.createElement('legend');
    legend.className = 'sr-only';
    legend.textContent = 'Phong cách dựng video';
    $('style-options').append(legend);

    const samples = {
      explainer: ['Ý TƯỞNG', 'THÀNH HÌNH'],
      inspirational: ['MỖI NGÀY', 'BỨT PHÁ'],
      real_estate: ['KHÔNG GIAN', 'ĐÁNG SỐNG']
    };

    for (const p of catalog) {
      const label = document.createElement('label');
      label.className = 'style-card';
      const demo = document.createElement('span');
      demo.className = `style-demo ${p.id}`;
      demo.setAttribute('aria-hidden', 'true');
      const phrase = document.createElement('span');
      phrase.textContent = samples[p.id]?.[0] || p.label;
      const b = document.createElement('b');
      b.textContent = samples[p.id]?.[1] || '';
      phrase.append(document.createElement('br'), b);
      demo.append(phrase);

      const copy = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = p.label;
      const desc = document.createElement('small');
      desc.textContent = p.description;
      copy.append(title, desc);

      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'style';
      input.value = p.id;
      input.onchange = () => {
        style = input.value;
        clearResult();
        showStyle();
        $('render-hint').textContent = 'Bấm dựng để xuất video theo phong cách vừa chọn.';
      };
      label.append(demo, copy, input);
      $('style-options').append(label);
    }

    $('connection').textContent = 'Đã kết nối tool';
    const last = localStorage.getItem('danava-last-video');
    if (last && !file) {
      const p = await api(`/api/projects/${last}`);
      if (p.video && !file) {
        project = p;
        source(p);
        style = p.job?.branding?.style_preset || p.edit_plan?.style_preset?.id || 'explainer';
        const radio = [...document.querySelectorAll('input[name="style"]')].find(el => el.value === style);
        if (radio) radio.checked = true;
        else style = '';
        showStyle();

        // Restore custom options & asset selections from project state
        const b = p.job?.branding || p.edit_plan?.branding || {};
        if (b.brand_name && $('input-brand-name')) $('input-brand-name').value = b.brand_name;
        if (p.edit_plan?.proper_names && $('input-proper-names')) $('input-proper-names').value = p.edit_plan.proper_names;
        if ((p.director?.user_prompt || b.prompt) && $('input-prompt')) $('input-prompt').value = p.director?.user_prompt || b.prompt || '';

        const assets = p.edit_plan?.assets || [];
        if (b.logo_asset_id && assets.some(a => a.id === b.logo_asset_id)) selectedLogoId = b.logo_asset_id;
        if (b.music_asset_id && assets.some(a => a.id === b.music_asset_id)) selectedMusicId = b.music_asset_id;
        if (Array.isArray(b.image_asset_ids)) {
          b.image_asset_ids.forEach(id => { if (assets.some(a => a.id === id)) selectedImageIds.add(id); });
        }
        if (Array.isArray(b.broll_asset_ids)) {
          b.broll_asset_ids.forEach(id => { if (assets.some(a => a.id === id)) selectedBrollIds.add(id); });
        }
        renderExtraAssets();

        if (active(p)) {
          controls(true);
          progress(p);
          poll();
        } else if (p.output_path && p.output_revision === p.revision && p.job?.status !== 'failed') {
          finish(p);
        } else if (p.job?.status === 'failed') {
          fail(p.job.error);
        }
      }
    } else {
      renderExtraAssets();
    }
  } catch (e) {
    $('connection').textContent = 'Chưa kết nối được tool';
    fail(e.message);
  }
  controls(busy);
}

initialize();

