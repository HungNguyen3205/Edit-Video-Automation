# DANAVA Video Studio — AI dựng video theo prompt

FastAPI + FFmpeg + JavaScript. Có hai chế độ riêng biệt: **AI theo yêu cầu** dùng model Ollama tại máy, và **hiệu ứng theo quy tắc** để dựng khi chưa có model. Không dùng khóa API trả phí hay dịch vụ render bên ngoài.

## Vì sao bản cũ vẫn dựng cố định?

`auto_plan()` chỉ thêm zoom theo khoảng 7/9/12 giây và trích vài chữ đầu phụ đề. Không có model đọc prompt; `audio_tracks` bị xóa khi xác thực. Bản này bổ sung `ai_director.py`: prompt + lời thoại + mốc chuyển cảnh/khoảng im lặng → quyết định AI có schema → kiểm tra tài nguyên/thời gian → FFmpeg → MP4 thật. Không dùng kế hoạch quy tắc để giả thành AI khi model lỗi.

## Cài và chạy trên Windows

Cần Python 3.10+, FFmpeg/FFprobe trong PATH, FFmpeg có libx264, drawtext và subtitles/libass. Font cần hỗ trợ tiếng Việt; có thể đặt `VIDEO_FONT_FILE` tới file TTF.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Để tự nhận dạng lời nói tiếng Việt:
pip install -r requirements-ai.txt
```

Cài [Ollama](https://ollama.com/download), mở ứng dụng Ollama, rồi tải model:

```powershell
ollama pull qwen3:4b
python main.py
```

Mở **http://127.0.0.1:8000/**. Model chạy tại máy qua HTTP localhost; đây là giao tiếp với runtime cục bộ, không phải API AI trả phí. Cài Whisper chỉ giúp nhận dạng lời nói, không thay thế model Ollama. Lần đầu tải model cần Internet; lần sau dùng model đã lưu. Model, Whisper và render có thể chậm trên CPU.

Trên Linux: cài `ffmpeg fonts-dejavu-core`, dùng `source .venv/bin/activate`, các lệnh Python/pip còn lại giống nhau. Bật dịch vụ Ollama (hoặc `ollama serve`) trước khi dựng AI.

## Cách dùng

1. Tạo dự án, tải video chính. Một video là đủ.
2. Chọn **AI theo yêu cầu**, nhập prompt hoặc bấm **Dùng yêu cầu gợi ý**.
3. Bật nhận dạng phụ đề nếu đã cài Whisper, hoặc nhập SRT trong phần chỉnh chi tiết. Lời thoại giúp AI hiểu nội dung video.
4. Có thể thêm ảnh/video minh họa và gắn từ khóa; thêm file nhạc MP3/WAV/M4A/AAC/OGG/FLAC qua **Thêm tài nguyên**, chọn nó trong **Nhạc nền**.
5. Bấm **AI dựng thử 12 giây** để lập kế hoạch cho toàn timeline rồi render 12 giây đầu của bản dựng. Bấm **Xuất bản đã chỉnh** để xuất toàn bộ cùng kế hoạch; bấm **Tự động dựng & xuất** nếu muốn AI lập lại kế hoạch.
6. Xem **AI đã dựng**, các cảnh báo và MP4 thực tế. Chỉnh đoạn, phụ đề, chữ, minh họa nếu cần, lưu rồi xuất lại.

Ví dụ prompt:

> Dựng video đủ wow cho Reels: mở đầu thu hút từ lời nói, bỏ khoảng im lặng dài, zoom ở ý quan trọng, chữ ngắn dễ đọc, thêm whoosh nhẹ và nhạc nền nhỏ nếu có. Giữ nguyên ý, không lạm dụng hiệu ứng.

Hoặc:

> Dựng nhẹ và trang trọng. Giữ thứ tự lời nói, không zoom, không thêm chữ nổi bật, không hiệu ứng âm thanh. Nhạc nền rất nhỏ, giữ phụ đề rõ ràng.

Model quyết định các đoạn giữ và thứ tự, điểm zoom, tiêu đề, minh họa, âm thanh nhấn và âm lượng nhạc theo yêu cầu. Engine hiện hỗ trợ cắt nối, zoom có easing, chữ có fade, phụ đề, minh họa góc/toàn khung, nhạc có fade/lặp/ducking và ba âm thanh tổng hợp whoosh/impact/chime. Chưa hỗ trợ speed ramp, chuyển cảnh phức tạp, tự tạo nhạc, tìm stock, tạo ảnh hay theo dõi khuôn mặt. Yêu cầu vượt khả năng cần được AI báo lại.

## Phân tích nội dung và giới hạn

- Mặc định model đọc lời thoại có timestamp, tên/từ khóa tài nguyên và mốc scene/silence; chưa dùng thị giác. Thiếu phụ đề sẽ hiện cảnh báo về mức hiểu lời nói.
- FFmpeg phân tích tối đa 120 giây đầu của mỗi đoạn; phạm vi phân tích được gửi rõ cho model. Prompt/ngữ cảnh quá dài bị từ chối thay vì cắt lén nội dung. Phù hợp nhất cho video ngắn; chia video dài thành dự án nhỏ.
- Tùy chọn **model thị giác**: đặt `VIDEO_AI_MODEL` tới model đã tải có hỗ trợ ảnh, và `VIDEO_AI_VISION=1` trước khi khởi động. Gửi tối đa 8 khung hình mẫu, không phải hiểu toàn bộ chuyển động. Model chỉ hỗ trợ text sẽ báo lỗi khi bật chế độ ảnh. Chế độ này chưa được kiểm thử với model thật trong môi trường phát triển.
- Không có nhạc tải lên thì không tự tạo nhạc nền. Âm thanh nhấn là âm tổng hợp đơn giản, không phải thư viện nhạc/âm thanh chuyên nghiệp.
- Chất lượng dựng phụ thuộc model, chất lượng transcript, tài nguyên và prompt. Cần nghe/xem bản thử, nhất là sau khi AI cắt lời nói. Model nhỏ có thể hiểu sai prompt; không có cam kết mọi video đều chuyên nghiệp.
- Kế hoạch model được kiểm tra và cho sửa lỗi một lần; không cho model cung cấp đường dẫn, lệnh shell hoặc filter FFmpeg. Model không sẵn sàng/sai kế hoạch sẽ báo lỗi, không báo thành công giả.
- Phụ đề giữ timestamp nguồn và tự ánh xạ sau khi cắt/reorder. Chỉnh sửa thủ công có thời gian được ánh xạ sang đoạn giữ lại; nội dung trong đoạn đã bỏ cũng bị bỏ. Chạy AI lần nữa dùng timeline hiện tại làm đầu vào, không phục hồi đoạn đã bỏ; có thể chỉnh clip nguồn hoặc tạo dự án mới để dựng lại từ gốc.

## Cấu hình

| Biến | Mặc định | Công dụng |
| --- | --- | --- |
| `VIDEO_DATA_DIR` | `./data` | Dự án, nguồn và kết quả |
| `MAX_UPLOAD_MB` | `500` | Giới hạn mỗi file |
| `WHISPER_MODEL` | `base` | Model nhận dạng lời nói trên CPU; `tiny` nhẹ hơn |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Runtime Ollama; cấu hình địa chỉ máy render riêng nếu cần |
| `VIDEO_AI_MODEL` | `qwen3:4b` | Tên model đã tải, tùy cấu hình máy |
| `VIDEO_AI_VISION` | `0` | Bật gửi khung hình tới model hỗ trợ ảnh |
| `VIDEO_FONT_FILE` | unset | Đường dẫn TTF hỗ trợ tiếng Việt |

Một tác vụ nặng chạy mỗi lần. Hủy render dừng FFmpeg; hủy nhận dạng/phân tích có hiệu lực ở ranh giới bước, hủy Ollama khi nhận chunk tiếp theo (read timeout 30 giây). Ollama giới hạn đọc phản hồi 10 phút sau khi nhận chunk. Sao lưu toàn bộ `data` trước khi cập nhật/chuyển máy. Ứng dụng đơn người dùng tại localhost; chưa dành cho public hosting/multi-worker.

API `POST /api/projects/{id}/auto-edit` nhận `planner: "ai"`, `prompt`, `music_asset_id` tùy chọn, `transcribe`, `preview`. Khi không chỉ định planner, API giữ `rules` để tương thích với client cũ. UI mặc định AI cho dự án mới. `GET /api/health` trả trạng thái Ollama/model.

## Kiểm thử

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --check frontend/app.js
```

Kiểm thử xuất FFmpeg thật cho cắt nối, phụ đề, minh họa, nhạc và âm thanh; xác thực/repair kế hoạch, hợp đồng HTTP streaming Ollama, thiếu model, revision và tương thích dự án cũ. Các test AI dùng phản hồi kiểm soát; không thay thế đánh giá sáng tạo/inference bằng model thật. Xem `PROJECT_STATUS.md`.
