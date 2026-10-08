import os
import json
import uuid
import shutil
import asyncio
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

app = FastAPI()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
ASSETS_DIR = DATA_DIR / "assets"
OUTPUTS_DIR = DATA_DIR / "outputs"
FRONTEND_DIR = BASE_DIR / "frontend"

for d in [PROJECTS_DIR, ASSETS_DIR, OUTPUTS_DIR, FRONTEND_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

tasks = {}

def get_empty_edit_plan():
    return {
        "schema_version": 1,
        "assets": [],
        "video_clips": [],
        "audio_tracks": [],
        "subtitles": [],
        "text_overlays": [],
        "visual_overlays": [],
        "effect_keyframes": [],
        "output_settings": {
            "width": 1280,
            "height": 720,
            "fps": 30
        }
    }

def save_project(project_id, data):
    with open(PROJECTS_DIR / f"{project_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_project(project_id):
    path = PROJECTS_DIR / f"{project_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def get_video_metadata(filepath: str):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration", "-of", "json", filepath]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            if data.get("streams"):
                return data["streams"][0]
    except Exception as e:
        print(f"Error ffprobe: {e}")
    return {}

@app.get("/api/projects")
def get_projects():
    projects = []
    for file in PROJECTS_DIR.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            projects.append({"id": data.get("id"), "name": data.get("name"), "updated_at": data.get("updated_at")})
    return sorted(projects, key=lambda x: x.get("updated_at", ""), reverse=True)

@app.post("/api/projects")
def create_project(name: str = Form(...)):
    project_id = str(uuid.uuid4())
    project = {
        "id": project_id,
        "name": name,
        "updated_at": "",
        "video": None,
        "export_status": "none",
        "transcribe_status": "none",
        "output_path": None,
        "edit_plan": get_empty_edit_plan()
    }
    project["edit_plan"]["project_id"] = project_id
    save_project(project_id, project)
    return project

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    p = load_project(project_id)
    if not p: raise HTTPException(404, "Not found")
    return p

@app.post("/api/projects/{project_id}/upload")
async def upload_video(project_id: str, file: UploadFile = File(...)):
    project = load_project(project_id)
    if not project: raise HTTPException(404)
    asset_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1].lower()
    safe_filename = f"{asset_id}{ext}"
    file_path = ASSETS_DIR / safe_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    if ext in ['.mp4', '.mov', '.webm']:
        meta = get_video_metadata(str(file_path))
        if not project.get("video"):
            project["video"] = {"asset_id": asset_id, "original_name": file.filename, "filename": safe_filename, "metadata": meta}
            duration = float(meta.get("duration", 0))
            project["edit_plan"]["video_clips"] = [{
                "id": str(uuid.uuid4()),
                "asset_id": asset_id,
                "source_in": 0,
                "source_out": duration,
                "timeline_start": 0,
                "duration": duration
            }]
    
    project["edit_plan"]["assets"].append({
        "id": asset_id, "type": "video" if ext in ['.mp4','.mov'] else "image", "filename": safe_filename, "original_name": file.filename
    })
    save_project(project_id, project)
    return project

@app.post("/api/projects/{project_id}/edit_plan")
async def save_edit_plan(project_id: str, plan: dict):
    project = load_project(project_id)
    if not project: raise HTTPException(404)
    project["edit_plan"] = plan
    save_project(project_id, project)
    return {"status": "ok"}

def _transcribe_worker(project_id: str):
    p = load_project(project_id)
    try:
        if not HAS_WHISPER:
            raise Exception("Whisper is not installed. Please wait for pip install to finish.")
        
        video_filename = p["video"]["filename"]
        audio_path = str(ASSETS_DIR / f"{project_id}_audio.wav")
        video_path = str(ASSETS_DIR / video_filename)
        
        # Extract audio
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path], check=True, capture_output=True)
        
        model = whisper.load_model("tiny")
        result = model.transcribe(audio_path, language="vi")
        
        subtitles = []
        for segment in result["segments"]:
            subtitles.append({
                "id": str(uuid.uuid4()),
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip()
            })
            
        p["edit_plan"]["subtitles"] = subtitles
        p["transcribe_status"] = "succeeded"
        save_project(project_id, p)
        
        # Clean up audio
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
    except Exception as e:
        print("Transcription failed:", str(e))
        p["transcribe_status"] = "failed"
        save_project(project_id, p)

@app.post("/api/projects/{project_id}/transcribe")
async def transcribe_video(project_id: str, background_tasks: BackgroundTasks):
    p = load_project(project_id)
    if not p or not p.get("video"): raise HTTPException(400)
    p["transcribe_status"] = "running"
    save_project(project_id, p)
    background_tasks.add_task(_transcribe_worker, project_id)
    return {"status": "running"}

def seconds_to_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generate_srt(project_id: str, subtitles: list):
    srt_path = str(OUTPUTS_DIR / f"{project_id}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, sub in enumerate(subtitles):
            start = seconds_to_srt_time(sub["start"])
            end = seconds_to_srt_time(sub["end"])
            f.write(f"{i+1}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{sub['text']}\n\n")
    return srt_path

async def render_task(project_id: str, output_file: str):
    tasks[project_id] = "running"
    try:
        p = load_project(project_id)
        clips = p["edit_plan"]["video_clips"]
        subs = p["edit_plan"].get("subtitles", [])
        overlays = p["edit_plan"].get("visual_overlays", [])
        
        if not clips: raise Exception("No clips to render")
        clip = clips[0]
        asset = next(a for a in p["edit_plan"]["assets"] if a["id"] == clip["asset_id"])
        video_file = str(ASSETS_DIR / asset["filename"])
        
        # Setup inputs
        cmd = ["ffmpeg", "-y"]
        cmd.extend(["-ss", str(clip["source_in"]), "-t", str(clip["duration"]), "-i", video_file])
        
        for ov in overlays:
            ov_asset = next((a for a in p["edit_plan"]["assets"] if a["id"] == ov["asset_id"]), None)
            if ov_asset:
                if ov_asset["filename"].lower().endswith(('.png', '.jpg', '.jpeg')):
                    cmd.extend(["-loop", "1", "-t", str(ov.get("duration", 5) + ov.get("timeline_start", 0)), "-i", str(ASSETS_DIR / ov_asset["filename"])])
                else:
                    cmd.extend(["-i", str(ASSETS_DIR / ov_asset["filename"])])
        
        filter_complex = ""
        # Base trim already done via inputs.
        current_v = "0:v"
        current_a = "0:a"
        
        # Add overlays
        filter_parts = []
        if overlays:
            for i, ov in enumerate(overlays):
                start = ov.get("timeline_start", 0)
                end = start + ov.get("duration", 5)
                # Overlay at (x,y), enable between start and end
                x = ov.get("x", 0)
                y = ov.get("y", 0)
                filter_parts.append(f"[{current_v}][{i+1}:v]overlay=x={x}:y={y}:enable='between(t,{start},{end})'[v{i+1}]")
                current_v = f"v{i+1}"
        
        # Add subtitles if any
        if subs:
            srt_path = generate_srt(project_id, subs)
            # escape windows path for ffmpeg
            safe_srt_path = srt_path.replace('\\', '/').replace(':', '\\:')
            filter_parts.append(f"[{current_v}]subtitles='{safe_srt_path}'[vsub]")
            current_v = "vsub"
            
        if filter_parts:
            filter_complex = ";".join(filter_parts)
            cmd.extend(["-filter_complex", filter_complex, "-map", f"[{current_v}]", "-map", current_a])
        else:
            cmd.extend(["-map", current_v, "-map", current_a])
            
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-c:a", "aac", output_file])
        
        print(f"Running ffmpeg: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        if proc.returncode == 0:
            tasks[project_id] = "succeeded"
            p = load_project(project_id)
            p["output_path"] = f"/outputs/{os.path.basename(output_file)}"
            p["export_status"] = "succeeded"
            save_project(project_id, p)
        else:
            print("FFMPEG ERROR:", err.decode())
            tasks[project_id] = "failed"
            p = load_project(project_id)
            p["export_status"] = "failed"
            save_project(project_id, p)
    except Exception as e:
        print("RENDER EXCEPTION:", str(e))
        tasks[project_id] = "failed"
        p = load_project(project_id)
        p["export_status"] = "failed"
        save_project(project_id, p)

@app.post("/api/projects/{project_id}/export")
async def export_project(project_id: str, background_tasks: BackgroundTasks):
    project = load_project(project_id)
    if not project: raise HTTPException(400)
    tasks[project_id] = "queued"
    out_name = f"{project_id}_output.mp4"
    project["export_status"] = "queued"
    save_project(project_id, project)
    background_tasks.add_task(render_task, project_id, str(OUTPUTS_DIR / out_name))
    return {"status": "queued"}

@app.get("/api/projects/{project_id}/status")
def get_status(project_id: str):
    p = load_project(project_id)
    return {
        "status": tasks.get(project_id, p.get("export_status", "none") if p else "none"),
        "transcribe_status": p.get("transcribe_status", "none") if p else "none"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
