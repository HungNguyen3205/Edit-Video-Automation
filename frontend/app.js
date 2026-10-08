let currentProjectId = null;
let currentProjectData = null;
let statusInterval = null;
const pixelsPerSecond = 20;

const el = {
    viewProjects: document.getElementById('view-projects'),
    viewSingleProject: document.getElementById('view-single-project'),
    projectList: document.getElementById('project-list'),
    newProjectName: document.getElementById('new-project-name'),
    btnCreateProject: document.getElementById('btn-create-project'),
    btnHome: document.getElementById('btn-home'),
    projectTitle: document.getElementById('project-title'),
    
    // Uploads
    uploadArea: document.getElementById('upload-area'),
    fileUpload: document.getElementById('file-upload'),
    videoInfo: document.getElementById('video-info'),
    vName: document.getElementById('v-name'),
    vDuration: document.getElementById('v-duration'),
    
    // Assets
    btnUploadAsset: document.getElementById('btn-upload-asset'),
    assetUpload: document.getElementById('asset-upload'),
    assetsList: document.getElementById('assets-list'),
    
    // Subtitles
    btnTranscribe: document.getElementById('btn-transcribe'),
    transcribeStatus: document.getElementById('transcribe-status'),
    subtitlesList: document.getElementById('subtitles-list'),
    
    // Player & Export
    mainPlayer: document.getElementById('main-player'),
    btnExport: document.getElementById('btn-export'),
    btnAutoEdit: document.getElementById('btn-auto-edit'),
    exportStatus: document.getElementById('export-status'),
    downloadLink: document.getElementById('download-link'),
    
    // Timeline
    btnPlay: document.getElementById('btn-play'),
    timeDisplay: document.getElementById('time-display'),
    trackMain: document.getElementById('track-main'),
    trackOverlay: document.getElementById('track-overlay'),
    
    // Editor
    clipEditor: document.getElementById('clip-editor'),
    clipStart: document.getElementById('clip-start'),
    clipDuration: document.getElementById('clip-duration'),
    btnSaveClip: document.getElementById('btn-save-clip'),
    toastContainer: document.getElementById('toast-container'),
    previewOverlay: document.getElementById('preview-overlay'),
};

function showToast(message, type = 'info') {
    el.toastContainer.textContent = message;
    el.toastContainer.style.background = type === 'error' ? '#e74c3c' : (type === 'success' ? '#2ecc71' : '#3498db');
    el.toastContainer.classList.remove('hidden');
    setTimeout(() => el.toastContainer.classList.add('hidden'), 5000);
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    document.querySelector(`button[onclick="switchTab('${tabId}')"]`).classList.add('active');
    document.getElementById(tabId).classList.remove('hidden');
}
window.switchTab = switchTab;

async function loadProjects() {
    const res = await fetch('/api/projects');
    const projects = await res.json();
    el.projectList.innerHTML = '';
    projects.forEach(p => {
        const card = document.createElement('div');
        card.className = 'project-card';
        card.textContent = p.name;
        card.onclick = () => openProject(p.id);
        el.projectList.appendChild(card);
    });
}

async function createProject() {
    const name = el.newProjectName.value.trim() || 'Untitled Project';
    const formData = new FormData();
    formData.append('name', name);
    const res = await fetch('/api/projects', { method: 'POST', body: formData });
    const p = await res.json();
    el.newProjectName.value = '';
    openProject(p.id);
}

async function openProject(id) {
    currentProjectId = id;
    const res = await fetch(`/api/projects/${id}`);
    const p = await res.json();
    currentProjectData = p;
    
    el.viewProjects.classList.add('hidden');
    el.viewSingleProject.classList.remove('hidden');
    el.projectTitle.textContent = p.name;
    
    if (p.video) {
        el.uploadArea.classList.add('hidden');
        el.videoInfo.classList.remove('hidden');
        el.vName.textContent = p.video.original_name;
        el.vDuration.textContent = p.video.metadata.duration ? parseFloat(p.video.metadata.duration).toFixed(2) : 'N/A';
        el.mainPlayer.src = `/assets/${p.video.filename}`;
    } else {
        el.uploadArea.classList.remove('hidden');
        el.videoInfo.classList.add('hidden');
        el.mainPlayer.src = '';
    }
    
    renderTimeline();
    renderAssets();
    renderSubtitles();
    updateStatuses();
    startStatusPolling();
}

function renderAssets() {
    el.assetsList.innerHTML = '';
    if(!currentProjectData || !currentProjectData.edit_plan) return;
    const assets = currentProjectData.edit_plan.assets || [];
    assets.forEach(a => {
        const div = document.createElement('div');
        div.className = 'asset-item';
        div.innerHTML = `<strong>${a.type}</strong><br/>${a.original_name}<br/>
            <button style="margin-top:5px;font-size:0.7em" onclick="addToTimeline('${a.id}')">+ Timeline</button>`;
        el.assetsList.appendChild(div);
    });
}

window.addToTimeline = async function(assetId) {
    if(!currentProjectData) return;
    const plan = currentProjectData.edit_plan;
    if(!plan.visual_overlays) plan.visual_overlays = [];
    plan.visual_overlays.push({
        id: "ov_" + Date.now(),
        asset_id: assetId,
        timeline_start: el.mainPlayer.currentTime || 0,
        duration: 5,
        x: 50,
        y: 50
    });
    await savePlan(plan);
};

function renderSubtitles() {
    el.subtitlesList.innerHTML = '';
    if(!currentProjectData || !currentProjectData.edit_plan || !currentProjectData.edit_plan.subtitles) return;
    currentProjectData.edit_plan.subtitles.forEach(sub => {
        const div = document.createElement('div');
        div.className = 'sub-item';
        div.textContent = `[${sub.start.toFixed(1)}s -> ${sub.end.toFixed(1)}s] ${sub.text}`;
        el.subtitlesList.appendChild(div);
    });
}

function renderTimeline() {
    el.trackMain.innerHTML = '';
    el.trackOverlay.innerHTML = '';
    el.clipEditor.classList.add('hidden');
    
    if (!currentProjectData || !currentProjectData.edit_plan) return;
    const plan = currentProjectData.edit_plan;
    
    // Main video
    (plan.video_clips || []).forEach((clip, index) => {
        const clipEl = document.createElement('div');
        clipEl.className = 'clip';
        clipEl.textContent = `Main Clip`;
        clipEl.style.left = `${clip.timeline_start * pixelsPerSecond}px`;
        clipEl.style.width = `${clip.duration * pixelsPerSecond}px`;
        clipEl.onclick = () => setupEditor(clip, clipEl, plan, 'clip');
        el.trackMain.appendChild(clipEl);
    });
    
    // Overlays
    el.previewOverlay.innerHTML = '';
    (plan.visual_overlays || []).forEach((ov, index) => {
        const clipEl = document.createElement('div');
        clipEl.className = 'clip overlay-clip';
        clipEl.textContent = `Overlay`;
        clipEl.style.left = `${ov.timeline_start * pixelsPerSecond}px`;
        clipEl.style.width = `${ov.duration * pixelsPerSecond}px`;
        clipEl.onclick = () => setupEditor(ov, clipEl, plan, 'overlay');
        el.trackOverlay.appendChild(clipEl);
        
        // Add preview image
        const asset = plan.assets.find(a => a.id === ov.asset_id);
        if(asset && asset.type === 'image') {
            const img = document.createElement('img');
            img.src = `/assets/${asset.filename}`;
            img.style.position = 'absolute';
            img.style.left = `${ov.x}px`;
            img.style.top = `${ov.y}px`;
            img.style.maxWidth = '30%';
            img.style.opacity = '0.8';
            img.style.border = '2px dashed #ff9800';
            el.previewOverlay.appendChild(img);
        }
    });
}

function setupEditor(item, domEl, plan, type) {
    document.querySelectorAll('.clip').forEach(c => c.classList.remove('active'));
    domEl.classList.add('active');
    el.clipEditor.classList.remove('hidden');
    
    if(type === 'clip') {
        el.clipStart.value = item.source_in;
        el.clipStart.previousElementSibling.textContent = "Source Start (s):";
    } else {
        el.clipStart.value = item.timeline_start;
        el.clipStart.previousElementSibling.textContent = "Timeline Start (s):";
    }
    el.clipDuration.value = item.duration;
    
    el.btnSaveClip.onclick = async () => {
        if(type === 'clip') item.source_in = parseFloat(el.clipStart.value);
        else item.timeline_start = parseFloat(el.clipStart.value);
        
        item.duration = parseFloat(el.clipDuration.value);
        await savePlan(plan);
    };
}

async function savePlan(plan) {
    await fetch(`/api/projects/${currentProjectId}/edit_plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(plan)
    });
    openProject(currentProjectId); // reload
}

async function uploadFile(file, isAsset=false) {
    if (!currentProjectId) return;
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`/api/projects/${currentProjectId}/upload`, { method: 'POST', body: formData });
    if(res.ok) openProject(currentProjectId);
}

el.uploadArea.onclick = () => el.fileUpload.click();
el.fileUpload.onchange = (e) => { if (e.target.files.length > 0) uploadFile(e.target.files[0], false); };

el.btnUploadAsset.onclick = () => el.assetUpload.click();
el.assetUpload.onchange = (e) => { if (e.target.files.length > 0) uploadFile(e.target.files[0], true); };

el.btnTranscribe.onclick = async () => {
    if (!currentProjectId) return;
    el.btnTranscribe.textContent = '⏳ Đang xử lý AI Whisper... Vui lòng đợi';
    el.btnTranscribe.disabled = true;
    showToast('Bắt đầu chạy nhận dạng giọng nói, việc này có thể mất vài phút...', 'info');
    await fetch(`/api/projects/${currentProjectId}/transcribe`, { method: 'POST' });
    startStatusPolling();
};

el.btnExport.onclick = async () => {
    if (!currentProjectId) return;
    el.btnExport.textContent = '⏳ Đang xuất video...';
    el.btnExport.disabled = true;
    showToast('Bắt đầu Render MP4, vui lòng đợi!', 'info');
    await fetch(`/api/projects/${currentProjectId}/export`, { method: 'POST' });
    startStatusPolling();
};

el.btnAutoEdit.onclick = async () => {
    if (!currentProjectData || !currentProjectData.edit_plan) return;
    const plan = currentProjectData.edit_plan;
    const asset = plan.assets ? plan.assets.find(a => a.type === 'image') : null;
    
    if(!asset) {
        showToast('Lỗi: Bạn phải tải lên ít nhất 1 bức ảnh ở tab Assets trước khi dùng Auto Edit!', 'error');
        return;
    }
    
    if(!plan.visual_overlays) plan.visual_overlays = [];
    if(plan.visual_overlays.length > 0) {
        showToast('Timeline đã có ảnh, hãy xóa (tạo Project mới) để thêm lại.', 'error');
        return;
    }

    plan.visual_overlays.push({
        id: "auto_" + Date.now(),
        asset_id: asset.id,
        timeline_start: 0,
        duration: 5,
        x: 50, y: 50
    });
    
    await savePlan(plan);
    showToast('Auto Edit thành công! Bức ảnh đã được chèn vào Timeline.', 'success');
};

function updateStatuses() {
    if(!currentProjectData) return;
    el.exportStatus.textContent = `Status: ${currentProjectData.export_status}`;
    el.transcribeStatus.textContent = `Status: ${currentProjectData.transcribe_status}`;
    
    if (currentProjectData.transcribe_status === 'succeeded' || currentProjectData.transcribe_status === 'failed') {
        el.btnTranscribe.textContent = '🎙️ Auto Transcribe (Whisper)';
        el.btnTranscribe.disabled = false;
    }
    if (currentProjectData.export_status === 'succeeded' || currentProjectData.export_status === 'failed') {
        el.btnExport.textContent = 'Render MP4';
        el.btnExport.disabled = false;
    }
    
    if (currentProjectData.export_status === 'succeeded' && currentProjectData.output_path) {
        el.downloadLink.href = currentProjectData.output_path;
        el.downloadLink.classList.remove('hidden');
    } else {
        el.downloadLink.classList.add('hidden');
    }
}

function startStatusPolling() {
    if (statusInterval) clearInterval(statusInterval);
    statusInterval = setInterval(async () => {
        if (!currentProjectId) return clearInterval(statusInterval);
        const res = await fetch(`/api/projects/${currentProjectId}/status`);
        const data = await res.json();
        if(currentProjectData) {
            currentProjectData.export_status = data.status;
            currentProjectData.transcribe_status = data.transcribe_status;
            updateStatuses();
            if(data.transcribe_status === 'succeeded' && (!currentProjectData.edit_plan.subtitles || currentProjectData.edit_plan.subtitles.length === 0)) {
                // reload fully to get subs
                openProject(currentProjectId);
            }
        }
    }, 2000);
}

el.mainPlayer.ontimeupdate = () => {
    const total = currentProjectData?.video?.metadata?.duration || 0;
    el.timeDisplay.textContent = `${el.mainPlayer.currentTime.toFixed(1)} / ${parseFloat(total).toFixed(1)}`;
};
el.btnPlay.onclick = () => { el.mainPlayer.paused ? el.mainPlayer.play() : el.mainPlayer.pause(); };
el.btnHome.onclick = () => {
    currentProjectId = null;
    if (statusInterval) clearInterval(statusInterval);
    el.viewProjects.classList.remove('hidden');
    el.viewSingleProject.classList.add('hidden');
    loadProjects();
};
el.btnCreateProject.onclick = createProject;

loadProjects();
