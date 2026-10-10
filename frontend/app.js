"use strict";
const $ = (id) => document.getElementById(id);
let project = null,
  health = null,
  intensity = "balanced",
  tab = "clips",
  dirty = false;
let polling = null,
  pollingBusy = false,
  activeView = "source",
  toastTimer,
  draft = null;
function icons() {
  window.lucide?.createIcons();
}
function node(tag, className = "", text = "") {
  const n = document.createElement(tag);
  n.className = className;
  n.textContent = text;
  return n;
}
function show(id, value = true) {
  $(id).classList.toggle("hidden", !value);
}
function notify(message, error = false) {
  $("toast").textContent = message;
  $("toast").classList.toggle("error-toast", error);
  show("toast");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => show("toast", false), error ? 9000 : 4500);
}
async function api(path, options = {}) {
  const res = await fetch(path, options);
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Máy chủ trả về dữ liệu không hợp lệ (${res.status}).`);
  }
  if (!res.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Yêu cầu thất bại (${res.status}).`,
    );
  return data;
}
function json(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
function busy() {
  return ["queued", "running"].includes(project?.job?.status);
}
function markDirty() {
  dirty = true;
  $("save-state").textContent = "Có thay đổi chưa lưu";
  updateStatus();
}
function duration() {
  return (draft?.video_clips || []).reduce((sum, c) => sum + c.duration, 0);
}
function clone(value) {
  return JSON.parse(JSON.stringify(value));
}
function errorWrap(fn) {
  return async (...args) => {
    try {
      await fn(...args);
    } catch (e) {
      notify(e.message, true);
    }
  };
}

async function loadProjects() {
  const list = await api("/api/projects");
  $("project-count").textContent = list.length;
  $("project-list").replaceChildren();
  if (!list.length)
    $("project-list").append(
      node(
        "div",
        "empty-projects",
        "Chưa có dự án. Tạo video đầu tiên của bạn ở phía trên.",
      ),
    );
  for (const p of list) {
    const card = node("button", "project-card");
    const thumb = node("div", "project-thumb");
    if (p.video) {
      const v = node("video");
      v.src = `/assets/${p.video.filename}#t=0.1`;
      v.muted = true;
      v.preload = "metadata";
      if (p.video.thumbnail) v.poster = `/assets/${p.video.thumbnail}`;
      thumb.append(v);
    } else {
      const icon = node("i");
      icon.dataset.lucide = "film";
      thumb.append(icon);
    }
    const body = node("div", "project-body");
    body.append(
      node("strong", "", p.name),
      node(
        "p",
        "",
        `${p.video ? `${Number(p.video.metadata.duration).toFixed(0)} giây` : "Chưa có video"} · ${p.updated_at ? new Date(p.updated_at).toLocaleDateString("vi-VN") : "Mới tạo"}`,
      ),
    );
    card.append(thumb, body);
    card.onclick = errorWrap(() => openProject(p.id));
    $("project-list").append(card);
  }
  icons();
}
async function home() {
  if (dirty && !confirm("Bạn có thay đổi chưa lưu. Rời bản dựng?")) return;
  clearInterval(polling);
  $("main-player").pause();
  project = null;
  draft = null;
  dirty = false;
  show("view-editor", false);
  show("view-projects");
  await loadProjects();
}
async function createProject(e) {
  e.preventDefault();
  $("btn-create-project").disabled = true;
  try {
    const form = new FormData();
    form.append("name", $("new-project-name").value.trim() || "Video mới");
    const p = await api("/api/projects", { method: "POST", body: form });
    $("new-project-name").value = "";
    await openProject(p.id);
  } finally {
    $("btn-create-project").disabled = false;
  }
}
async function openProject(id) {
  clearInterval(polling);
  project = await api(`/api/projects/${id}`);
  draft = clone(project.edit_plan);
  dirty = false;
  activeView = "source";
  intensity = draft.preset || "balanced";
  show("view-projects", false);
  show("view-editor");
  $("project-title").textContent = project.name;
  $("save-state").textContent = "Đã lưu";
  $("headline").value =
    draft.text_overlays.find(
      (t) => t.origin === "auto" && t.timeline_start === 0,
    )?.text || "";
  const outputRatio =
    draft.output_settings.width / draft.output_settings.height;
  const sourceRatio = project.video
    ? project.video.metadata.width / project.video.metadata.height
    : outputRatio;
  $("output-ratio").value =
    Math.abs(outputRatio - sourceRatio) < 0.01
      ? "original"
      : Math.abs(outputRatio - 9 / 16) < 0.01
        ? "portrait"
        : Math.abs(outputRatio - 16 / 9) < 0.01
          ? "landscape"
          : Math.abs(outputRatio - 1) < 0.01
            ? "square"
            : "original";
  document
    .querySelectorAll("[data-intensity]")
    .forEach((b) =>
      b.classList.toggle("selected", b.dataset.intensity === intensity),
    );
  $("auto-subs").checked = !!health?.whisper;
  $("edit-prompt").value = draft.director?.prompt || "";
  $("planner").value = draft.director?.engine === "ollama" || !draft.preset ? "ai" : "rules";
  updatePlanner();
  updateModelNote();
  renderAssets();
  renderEditList();
  setPlayer("source");
  updateStatus();
  poll();
}
function updatePlanner() {
  const ai = $("planner").value === "ai";
  show("ai-controls", ai);
  show("rules-controls", !ai);
  $("ai-note").textContent = health?.ai?.available
    ? `Ollama sẵn sàng · ${health.ai.model}. ${health.ai.vision ? "Có phân tích khung hình mẫu." : "Đọc lời thoại và phân tích mốc cảnh/âm thanh."}`
    : `Chưa có model AI. Cài Ollama, chạy: ollama pull ${health?.ai?.model || "qwen3:4b"}. Sau đó tải lại trang.`;
}
function updateModelNote() {
  const has = !!health?.whisper;
  $("model-note").textContent = has
    ? `Whisper đã cài · model ${health.model}. Lần đầu có thể cần tải model. Phụ đề luôn có thể sửa.`
    : "Chưa cài Whisper. Bạn vẫn có thể dựng zoom/chữ, hoặc nhập SRT. Để tự nhận dạng: pip install -r requirements-ai.txt";
  $("model-note").classList.toggle("good", has);
}
function resultPath() {
  if (
    project?.job?.status === "succeeded" &&
    project.job.mode !== "transcribe" &&
    project.preview_path &&
    project.preview_revision === project.revision &&
    project.job.preview
  )
    return project.preview_path;
  if (project?.output_path && project.output_revision === project.revision)
    return project.output_path;
  if (project?.preview_path && project.preview_revision === project.revision)
    return project.preview_path;
  return null;
}
function setPlayer(view) {
  activeView = view;
  const path =
    view === "result"
      ? resultPath()
      : project?.video
        ? `/assets/${project.video.filename}`
        : null;
  show("main-player", !!path);
  show("player-empty", !path);
  $("main-player").poster = project?.video?.thumbnail
    ? `/assets/${project.video.thumbnail}`
    : "";
  if (path && $("main-player").getAttribute("src") !== path) {
    $("main-player").src = path;
    $("main-player").load();
  }
  if (!path) {
    $("main-player").removeAttribute("src");
    $("main-player").load();
  }
  $("show-source").classList.toggle("selected", view === "source");
  $("show-result").classList.toggle("selected", view === "result");
  $("viewer-label").textContent =
    view === "result"
      ? "Bản dựng đã render · hiệu ứng được ghi vào video"
      : project?.video?.original_name || "Chưa có video";
  const m = project?.video?.metadata;
  $("video-meta").textContent = m
    ? `${m.width} × ${m.height} · ${Number(m.duration).toFixed(1)}s`
    : "—";
}
async function uploadFile(file, role) {
  if (!project) return;
  const id = project.id;
  if (busy())
    throw new Error(
      "Đợi tác vụ hoàn thành hoặc hủy trước khi thêm tài nguyên.",
    );
  if (dirty) await savePlan();
  notify(`Đang tải ${file.name}…`);
  const form = new FormData();
  form.append("file", file);
  form.append("role", role);
  const updated = await api(`/api/projects/${id}/upload`, {
    method: "POST",
    body: form,
  });
  if (project?.id !== id) return;
  project = updated;
  draft = clone(project.edit_plan);
  dirty = false;
  renderAssets();
  renderEditList();
  updateStatus();
  if (role === "main") setPlayer("source");
  notify(
    role === "main"
      ? "Video đã sẵn sàng. Chọn cách dựng rồi bấm Tự động dựng & xuất."
      : "Đã thêm minh họa. Gắn từ khóa hoặc chèn thủ công.",
  );
}
function renderAssets() {
  $("assets-list").replaceChildren();
  show("upload-area", !project?.video);
  const selectedMusic = $("music-asset").value;
  $("music-asset").replaceChildren();
  const none = node("option", "", "Không có nhạc nền");
  none.value = "";
  $("music-asset").append(none);
  for (const a of (draft?.assets || []).filter(a => a.type === "audio")) {
    const option = node("option", "", a.original_name);
    option.value = a.id;
    $("music-asset").append(option);
  }
  $("music-asset").value = selectedMusic || draft.audio_tracks?.find(t => t.kind === "music")?.asset_id || "";
  const main = new Set((draft?.video_clips || []).map((c) => c.asset_id));
  for (const a of draft?.assets || []) {
    const card = node("div", "asset-card");
    const media = node(a.type === "image" ? "img" : a.type === "audio" ? "audio" : "video");
    media.src = `/assets/${a.filename}`;
    if (a.type === "image") media.alt = a.original_name;
    else {
      media.controls = a.type === "audio";
      media.muted = a.type !== "audio";
      media.preload = "metadata";
      if (a.thumbnail) media.poster = `/assets/${a.thumbnail}`;
    }
    card.append(media, node("strong", "", a.original_name));
    if (main.has(a.id))
      card.append(node("span", "helper muted", "Video chính"));
    else if (a.type === "audio") {
      card.append(node("span", "helper muted", "Nhạc nền · chọn trong phần yêu cầu AI"));
    } else {
      const input = node("input");
      input.placeholder = "Từ khóa: ứng dụng, lịch lớp";
      input.value = a.keywords || "";
      input.setAttribute("aria-label", `Từ khóa ${a.original_name}`);
      input.oninput = () => {
        a.keywords = input.value;
        markDirty();
      };
      const add = node("button", "secondary small", "Chèn vào bản dựng");
      add.disabled = !project.video || busy();
      add.onclick = () => {
        const start = Math.min(
          Math.max(0, $("main-player").currentTime || 0),
          Math.max(0, duration() - 0.1),
        );
        const d = Math.min(
          3,
          duration() - start,
          a.type === "video" ? a.metadata.duration : 3,
        );
        draft.visual_overlays.push({
          id: crypto.randomUUID(),
          asset_id: a.id,
          origin: "manual",
          timeline_start: start,
          duration: d,
          source_in: 0,
          x: 0.05,
          y: 0.1,
          width: 0.4,
          mode: "pip",
        });
        tab = "visual_overlays";
        markDirty();
        $("advanced").open = true;
        renderEditList();
      };
      card.append(input, add);
    }
    $("assets-list").append(card);
  }
}
function field(container, item, key, label, type = "number", wide = false) {
  const wrap = node("label", wide ? "wide" : "", label);
  const input = node(type === "textarea" ? "textarea" : "input");
  if (type !== "textarea") input.type = type;
  if (type === "number") {
    input.step = ".01";
    input.min = "0";
  }
  input.value = item[key] ?? "";
  input.oninput = () => {
    item[key] = type === "number" ? Number(input.value) : input.value;
    item.origin = "manual";
    markDirty();
  };
  wrap.append(input);
  container.append(wrap);
}
function renderEditList() {
  $("edit-list").replaceChildren();
  document
    .querySelectorAll("[data-tab]")
    .forEach((b) => b.classList.toggle("selected", b.dataset.tab === tab));
  show("btn-transcribe", tab === "subtitles");
  show("srt-label", tab === "subtitles");
  show("download-srt", tab === "subtitles");
  show("add-item", tab === "subtitles" || tab === "text_overlays");
  $("download-srt").href = `/api/projects/${project.id}/subtitles.srt`;
  const help = {
    clips:
      "Điểm đầu tính trên video nguồn. Các đoạn được ghép theo thứ tự. Sau khi đổi thời lượng, hãy dựng lại hiệu ứng.",
    subtitles:
      "Thời gian phụ đề tính trên video nguồn. Studio tự ánh xạ khi cắt video.",
    text_overlays:
      "Thời gian tính trên bản dựng. Chữ hiển thị ở phía trên, có fade vào/ra.",
    visual_overlays:
      "Thời gian tính trên bản dựng. Tọa độ 0–1 tương ứng với tỷ lệ khung hình.",
  };
  $("tab-help").textContent = help[tab];
  const key = tab === "clips" ? "video_clips" : tab;
  const items = draft[key] || [];
  if (!items.length)
    $("edit-list").append(
      node(
        "p",
        "helper muted",
        "Chưa có đối tượng. Tự động dựng hoặc thêm thủ công.",
      ),
    );
  items.forEach((item, index) => {
    const row = node("div", "edit-row");
    const header = node("div", "edit-row-header");
    header.append(
      node(
        "strong",
        "",
        `${tab === "clips" ? "Đoạn video" : "Đối tượng"} ${index + 1}`,
      ),
    );
    if (tab !== "clips" || items.length > 1) {
      const remove = node("button", "", "Xóa");
      remove.onclick = () => {
        items.splice(index, 1);
        markDirty();
        renderEditList();
      };
      header.append(remove);
    }
    const fields = node("div", "edit-fields");
    if (tab === "clips") {
      field(fields, item, "source_in", "Điểm đầu nguồn (giây)");
      field(fields, item, "duration", "Thời lượng (giây)");
    } else if (tab === "subtitles") {
      field(fields, item, "start", "Bắt đầu nguồn (giây)");
      field(fields, item, "end", "Kết thúc nguồn (giây)");
      field(fields, item, "text", "Nội dung", "textarea", true);
    } else {
      field(fields, item, "timeline_start", "Bắt đầu bản dựng (giây)");
      field(fields, item, "duration", "Thời lượng (giây)");
      if (tab === "text_overlays")
        field(fields, item, "text", "Chữ nhấn mạnh", "textarea", true);
      else {
        const a = draft.assets.find((a) => a.id === item.asset_id);
        fields.append(
          node(
            "span",
            "wide helper muted",
            a?.original_name || "Tài nguyên không tồn tại",
          ),
        );
        field(fields, item, "x", "Vị trí ngang (0–1)");
        field(fields, item, "y", "Vị trí dọc (0–1)");
        field(fields, item, "width", "Chiều rộng (0.1–1)");
        if (a?.type === "video")
          field(fields, item, "source_in", "Điểm đầu video minh họa");
        const label = node("label", "", "Bố cục");
        const select = node("select");
        for (const [value, text] of [
          ["pip", "Góc khung hình"],
          ["full", "Toàn khung"],
        ]) {
          const opt = node("option", "", text);
          opt.value = value;
          select.append(opt);
        }
        select.value = item.mode || "pip";
        select.onchange = () => {
          item.mode = select.value;
          item.origin = "manual";
          markDirty();
        };
        label.append(select);
        fields.append(label);
      }
    }
    row.append(header, fields);
    $("edit-list").append(row);
  });
}
function applyRatio() {
  const ratio = $("output-ratio").value;
  let w, h;
  if (ratio === "original") {
    const m = project.video?.metadata;
    if (!m) return;
    const scale = Math.min(1, 1080 / Math.max(m.width, m.height));
    w = Math.max(120, Math.floor((m.width * scale) / 2) * 2);
    h = Math.max(120, Math.floor((m.height * scale) / 2) * 2);
  } else
    [w, h] = {
      portrait: [720, 1280],
      landscape: [1280, 720],
      square: [1080, 1080],
    }[ratio];
  draft.output_settings = {
    ...draft.output_settings,
    width: w,
    height: h,
    fit: "contain",
  };
}
async function savePlan() {
  if (!project?.video)
    throw new Error("Tải video chính trước khi lưu bản dựng.");
  const id = project.id;
  const updated = await api(
    `/api/projects/${id}/edit_plan`,
    json("POST", { plan: draft, revision: project.revision }),
  );
  if (project?.id !== id) return;
  project = updated;
  draft = clone(project.edit_plan);
  dirty = false;
  $("save-state").textContent = "Đã lưu";
  updateStatus();
}
async function startJob(mode, preview = false, forcePlanner = null) {
  if (!project?.video) throw new Error("Tải video chính trước khi bắt đầu.");
  if (busy()) return;
  if (dirty) await savePlan();
  const id = project.id;
  const options = {
    intensity,
    planner: forcePlanner || $("planner").value,
    prompt: $("edit-prompt").value.trim(),
    music_asset_id: $("music-asset").value,
    headline: $("headline").value.trim(),
    transcribe: $("auto-subs").checked,
    preview,
    use_current_plan: $("use-current-plan") ? $("use-current-plan").checked : false,
    duration_policy: $("duration-policy") ? $("duration-policy").value : "preserve",
    target_duration: $("target-duration") ? (parseFloat($("target-duration").value) || 0.0) : 0.0
  };
  const updated = await api(
    `/api/projects/${id}/${mode}`,
    json("POST", options),
  );
  if (project?.id !== id) return;
  project = updated;
  updateStatus();
  poll();
}
function updateStatus() {
  const job = project?.job;
  const running = busy();
  const director = project?.edit_plan?.director;
  $("director-summary").textContent = director ? `AI đã dựng: ${director.summary}` : "";
  show("director-summary", !!director);
  const hasVideo = !!project?.video;
  for (const id of [
    "btn-auto-edit",
    "btn-ai-preview",
    "btn-export",
    "btn-preview",
    "btn-transcribe",
    "btn-save",
    "btn-rules-edit",
  ])
    if ($(id)) $(id).disabled = running || !hasVideo;
  $("file-upload").disabled = running;
  $("asset-upload").disabled = running;
  $("srt-upload").disabled = running;
  $("status-badge").textContent =
    {
      queued: "Đang chờ",
      running: "Đang xử lý",
      succeeded: "Sẵn sàng",
      failed: "Có lỗi",
      cancelled: "Đã hủy",
    }[job?.status] || "Chưa dựng";
  $("status-badge").classList.toggle("good", job?.status === "succeeded");
  $("job-phase").textContent = job?.phase || "Bản dựng sẽ xuất hiện tại đây.";
  show("job-progress", running);
  if (job?.progress == null) $("job-progress").removeAttribute("value");
  else $("job-progress").value = job.progress;
  $("job-error").textContent = job?.error || "";
  show("job-error", !!job?.error);
  $("job-warnings").textContent = (job?.warnings || []).join(" ");
  show("job-warnings", !!job?.warnings?.length);
  show("btn-cancel", running);
  const validOutput =
    project?.output_path &&
    project.output_revision === project.revision &&
    !dirty;
  show("download-link", !!validOutput);
  if (validOutput) $("download-link").href = project.output_path;
  const validResult = !!resultPath() && !dirty;
  $("show-result").disabled = !validResult;
  $("result-note").textContent = dirty
    ? "Có chỉnh sửa chưa lưu. Lưu và xuất lại để cập nhật kết quả."
    : project?.output_path && !validOutput
      ? "Bản dựng đã thay đổi. Xuất lại để nhận video mới nhất."
      : "Xem thử và MP4 dùng cùng một bản dựng.";
  $("step-upload").className = hasVideo ? "done" : "active";
  $("step-edit").className =
    hasVideo && !validResult ? "active" : validResult ? "done" : "";
  $("step-result").className = validResult ? "active" : "";
}
function poll() {
  clearInterval(polling);
  if (!busy()) return;
  polling = setInterval(async () => {
    if (!project || pollingBusy) return;
    const id = project.id;
    pollingBusy = true;
    try {
      const latest = await api(`/api/projects/${id}`);
      if (project?.id !== id) return;
      const wasBusy = busy();
      const revisionChanged = latest.revision !== project.revision;
      project = latest;
      if (revisionChanged && !dirty) {
        draft = clone(project.edit_plan);
        renderAssets();
        renderEditList();
      }
      updateStatus();
      if (!busy()) {
        clearInterval(polling);
        if (wasBusy && project.job?.status === "succeeded") {
          if (!dirty && resultPath()) setPlayer("result");
          notify(project.job.phase);
        }
      }
    } catch (e) {
      notify(e.message, true);
      clearInterval(polling);
    } finally {
      pollingBusy = false;
    }
  }, 1000);
}
$("create-form").onsubmit = errorWrap(createProject);
$("btn-home").onclick = errorWrap(home);
$("btn-back").onclick = errorWrap(home);
$("file-upload").onchange = errorWrap(async (e) => {
  if (e.target.files[0]) await uploadFile(e.target.files[0], "main");
  e.target.value = "";
});
$("asset-upload").onchange = errorWrap(async (e) => {
  for (const file of e.target.files) await uploadFile(file, "asset");
  e.target.value = "";
});
$("upload-area").onkeydown = (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    $("file-upload").click();
  }
};
for (const event of ["dragenter", "dragover"])
  $("upload-area").addEventListener(event, (e) => {
    e.preventDefault();
    $("upload-area").classList.add("dragging");
  });
for (const event of ["dragleave", "drop"])
  $("upload-area").addEventListener(event, (e) => {
    e.preventDefault();
    $("upload-area").classList.remove("dragging");
  });
$("upload-area").addEventListener(
  "drop",
  errorWrap(async (e) => {
    const file = e.dataTransfer.files[0];
    if (file) await uploadFile(file, "main");
  }),
);
$("main-player").onerror = () =>
  notify(
    "Trình duyệt không phát được định dạng này. Thử Chrome/Edge mới hoặc tải MP4 để xem.",
    true,
  );
$("show-source").onclick = () => setPlayer("source");
$("show-result").onclick = () => setPlayer("result");
for (const b of document.querySelectorAll("[data-intensity]"))
  b.onclick = () => {
    intensity = b.dataset.intensity;
    document
      .querySelectorAll("[data-intensity]")
      .forEach((n) => n.classList.toggle("selected", n === b));
  };
for (const b of document.querySelectorAll("[data-tab]"))
  b.onclick = () => {
    tab = b.dataset.tab;
    renderEditList();
  };
$("output-ratio").onchange = () => {
  if (project?.video) {
    applyRatio();
    markDirty();
  }
};
$("btn-save").onclick = errorWrap(async () => {
  await savePlan();
  renderEditList();
  notify("Đã lưu chỉnh sửa.");
});
$("planner").onchange = updatePlanner;
$("prompt-example").onclick = () => {
  $("edit-prompt").value = "Dựng video đủ wow cho Reels: mở đầu thu hút từ lời nói, bỏ khoảng im lặng dài, zoom ở ý quan trọng, chữ ngắn dễ đọc, thêm whoosh nhẹ và nhạc nền nhỏ nếu có. Giữ nguyên ý, không lạm dụng hiệu ứng.";
};
$("btn-ai-preview").onclick = errorWrap(() => startJob("auto-edit", true, "ai"));
$("btn-auto-edit").onclick = errorWrap(() => startJob("auto-edit", false, "ai"));
if ($("btn-rules-edit")) {
  $("btn-rules-edit").onclick = errorWrap(() => startJob("auto-edit", false, "rules"));
}
$("btn-preview").onclick = errorWrap(() => startJob("export", true));
$("btn-export").onclick = errorWrap(() => startJob("export"));
$("btn-transcribe").onclick = errorWrap(() => startJob("transcribe"));
$("btn-cancel").onclick = errorWrap(async () => {
  const response = await api(`/api/projects/${project.id}/cancel`, {
    method: "POST",
  });
  notify(response.note);
});
$("srt-upload").onchange = errorWrap(async (e) => {
  if (!e.target.files[0]) return;
  if (dirty) await savePlan();
  const f = new FormData();
  f.append("file", e.target.files[0]);
  project = await api(`/api/projects/${project.id}/subtitles/import`, {
    method: "POST",
    body: f,
  });
  draft = clone(project.edit_plan);
  dirty = false;
  renderEditList();
  updateStatus();
  notify("Đã nhập phụ đề.");
  e.target.value = "";
});
$("add-item").onclick = () => {
  if (!project?.video) return;
  const total = duration();
  if (tab === "subtitles")
    draft.subtitles.push({
      id: crypto.randomUUID(),
      asset_id: project.video.asset_id,
      start: 0,
      end: Math.min(3, total),
      text: "Nhập phụ đề",
    });
  else if (tab === "text_overlays")
    draft.text_overlays.push({
      id: crypto.randomUUID(),
      origin: "manual",
      timeline_start: 0,
      duration: Math.min(3, total),
      text: "Nhập chữ nổi bật",
    });
  markDirty();
  renderEditList();
};
if ($("duration-policy")) {
  $("duration-policy").addEventListener("change", () => {
    $("target-dur-label").style.display = $("duration-policy").value === "summarize" ? "flex" : "none";
  });
}
window.addEventListener("beforeunload", (e) => {
  if (dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
(async () => {
  try {
    health = await api("/api/health");
    if (!health.ffmpeg || !health.ffprobe) {
      $("health-banner").textContent =
        "Cần cài FFmpeg và FFprobe vào PATH để dựng video.";
      show("health-banner");
    }
    await loadProjects();
    icons();
  } catch (e) {
    notify(e.message, true);
  }
})();
