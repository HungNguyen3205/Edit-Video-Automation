# DANAVA Video Studio — AI dựng video theo prompt

Giao diện chính chỉ có **video + prompt + Tạo video của tôi**. Xem [hướng dẫn chuẩn bị máy](docs/APPROVED_STYLE.md).

FastAPI + FFmpeg + JavaScript. Có hai chế độ riêng biệt: **AI theo yêu cầu** dùng model Ollama tại máy, và **hiệu ứng theo quy tắc** để dựng khi chưa có model. Không dùng khóa API trả phí hay dịch vụ render bên ngoài.

## Vì sao bản cũ vẫn dựng cố định?

`auto_plan()` chỉ thêm zoom theo khoảng 7/9/12 giây và trích vài chữ đầu phụ đề. Không có model đọc prompt; `audio_tracks` bị xóa khi xác thực. Bản này bổ sung `backend/ai_director.py`: prompt + lời thoại + mốc chuyển cảnh/khoảng im lặng → quyết định AI có schema → kiểm tra tài nguyên/thời gian → FFmpeg → MP4 thật. Không dùng kế hoạch quy tắc để giả thành AI khi model lỗi.

## Cài và chạy trên Windows

Cần Python 3.10+, FFmpeg/FFprobe trong PATH, FFmpeg có libx264, drawtext và subtitles/libass. Font cần hỗ trợ tiếng Việt; có thể đặt `VIDEO_FONT_FILE` tới file TTF.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Để tự nhận dạng lời nói tiếng Việt:
pip install -r requirements/requirements-ai-fast.txt
npm --prefix motion_engine install
```

Cài [Ollama](https://ollama.com/download), mở ứng dụng Ollama, rồi tải model:

```powershell
ollama pull qwen3:4b
python main.py
```

Mở **http://127.0.0.1:8000/**. Model chạy tại máy qua HTTP localhost; đây là giao tiếp với runtime cục bộ, không phải API AI trả phí. Cài Whisper chỉ giúp nhận dạng lời nói, không thay thế model Ollama. Lần đầu tải model cần Internet; lần sau dùng model đã lưu. Model, Whisper và render có thể chậm trên CPU.

Trên Linux: cài `ffmpeg fonts-dejavu-core`, dùng `source .venv/bin/activate`, các lệnh Python/pip còn lại giống nhau. Bật dịch vụ Ollama (hoặc `ollama serve`) trước khi dựng AI.

## Cách dùng giao diện mới

1. Thả **một video** vào trang chính.
2. Nhập yêu cầu nếu muốn; để trống thì dùng phong cách mẫu đã duyệt.
3. Bấm **Tạo video của tôi**. Tool tự nhận dạng lời nói, chọn cảnh/chữ/minh họa/SFX và xuất toàn bộ MP4; xem và tải ngay ở bên phải.

Không cần tạo tên dự án, chọn model, chọn style, nhập thời lượng, chỉnh timeline hoặc thêm từng hiệu ứng. Video được giữ trong **Video của tôi**; tải lại trang có thể tiếp tục theo dõi tác vụ hoặc mở kết quả. Khi muốn thay video, bấm vùng chọn video và đưa file mới vào.

`POST /api/projects/{id}/make-video` chỉ nhận `{ "prompt": "..." }`. Máy chủ tự chọn AI, profile mẫu, nhận dạng khi nguồn có tiếng, giữ toàn bộ thời lượng và render đầy đủ. Model chọn nội dung hình ảnh theo các đoạn lời nói; engine quản lý thời gian và kiểm tra MP4. Các thiết lập này không được đẩy sang form của người dùng.

Ví dụ: “Dựng đẹp và sinh động, chữ lớn rõ, minh họa đúng lời nói, SFX nhẹ; giữ người nói ở đầu và cuối.” Có thể yêu cầu phong cách nhẹ, không zoom/không SFX/không phụ đề.

Giao diện chỉnh thủ công cũ còn ở `/frontend/advanced.html` cho người cần sửa SRT/timeline/tài nguyên. Nó không phải bước bắt buộc của luồng mới.

Xem [docs/APPROVED_STYLE.md](docs/APPROVED_STYLE.md) để chuẩn bị máy một lần. Đây vẫn là AI cục bộ: Ollama và bộ nhận dạng cần được cài trước khi dựng; không giả thành AI khi thiếu model.

## Phân tích nội dung và giới hạn

- Mặc định model đọc lời thoại có timestamp, tên/từ khóa tài nguyên và mốc scene/silence; chưa dùng thị giác. Thiếu phụ đề sẽ hiện cảnh báo về mức hiểu lời nói.
- FFmpeg phân tích tối đa 120 giây đầu của mỗi đoạn; phạm vi phân tích được gửi rõ cho model. Prompt/ngữ cảnh quá dài bị từ chối thay vì cắt lén nội dung. Phù hợp nhất cho video ngắn; chia video dài thành dự án nhỏ.
- Tùy chọn **model thị giác**: đặt `VIDEO_AI_MODEL` tới model đã tải có hỗ trợ ảnh, và `VIDEO_AI_VISION=1` trước khi khởi động. Gửi tối đa 8 khung hình mẫu, không phải hiểu toàn bộ chuyển động. Model chỉ hỗ trợ text sẽ báo lỗi khi bật chế độ ảnh. Chế độ này chưa được kiểm thử với model thật trong môi trường phát triển.
- Cần Node.js và Chrome/Chromium để dựng phong cách mẫu; chạy `npm --prefix motion_engine install`. Có thể đặt `CHROME_PATH` nếu Chrome cài nơi khác.
- Không có nhạc tải lên thì không tự tạo nhạc nền. Âm thanh nhấn là âm tổng hợp đơn giản, không phải thư viện nhạc/âm thanh chuyên nghiệp.
- Chất lượng dựng phụ thuộc model, chất lượng transcript, tài nguyên và prompt. Cần nghe/xem bản thử, nhất là sau khi AI cắt lời nói. Model nhỏ có thể hiểu sai prompt; không có cam kết mọi video đều chuyên nghiệp.
- Kế hoạch model được kiểm tra và cho sửa lỗi tối đa hai lần trong luồng một nút (một lần ở trang nâng cao); không cho model cung cấp đường dẫn, lệnh shell hoặc filter FFmpeg. Model không sẵn sàng/sai kế hoạch sẽ báo lỗi, không báo thành công giả.
- Phụ đề giữ timestamp nguồn và tự ánh xạ sau khi cắt/reorder. Chỉnh sửa thủ công có thời gian được ánh xạ sang đoạn giữ lại; nội dung trong đoạn đã bỏ cũng bị bỏ. Nút Tạo video của tôi luôn dựng lại từ nguồn gốc và bản nhận dạng gốc. Trang nâng cao chỉ dùng timeline hiện tại khi người dùng chọn dùng bản hiện tại làm đầu vào.

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

API `POST /api/projects/{id}/auto-edit` nhận `planner: "ai"`, `prompt`, `music_asset_id` tùy chọn, `transcribe`, `preview`. Khi không chỉ định planner, API giữ `rules` để tương thích với client cũ. Giao diện chính luôn dùng luồng AI tự động; trang nâng cao vẫn giữ API và chế độ cũ. `GET /api/health` trả trạng thái Ollama/model.

## Kiểm thử

```bash
pip install -r requirements/requirements-dev.txt
python -m pytest -q
node --check frontend/app.js
```

Kiểm thử xuất FFmpeg thật cho cắt nối, phụ đề, minh họa, nhạc và âm thanh; xác thực/repair kế hoạch, hợp đồng HTTP streaming Ollama, thiếu model, revision và tương thích dự án cũ. Các test AI dùng phản hồi kiểm soát; không thay thế đánh giá sáng tạo/inference bằng model thật. Xem `docs/PROJECT_STATUS.md`.


## Cấu trúc thư mục

| Thư mục | Nội dung |
| --- | --- |
| `backend/` | AI planner, timeline, phụ đề, minh họa, renderer và bộ nhớ phản hồi |
| `skills/` | Toàn bộ skill, mẫu phong cách và tài liệu hướng dẫn học |
| `docs/` | Tài liệu cài đặt, sửa lỗi và báo cáo kiểm thử |
| `frontend/` | Giao diện web |
| `motion_engine/` | Dựng đồ họa chuyển động và font |
| `requirements/` | Dependency nhận dạng AI và kiểm thử tùy chọn |
| `scripts/` | Tiện ích; tạo âm thanh bằng `python scripts/generate_sfx.py` |
| `tests/` | Kiểm thử và file mẫu cũ trong `fixtures/legacy/` |
| `data/` | Dữ liệu chạy cục bộ, giữ nguyên vị trí và không đưa lên Git |

Lệnh khởi động vẫn là **`python main.py`** hoặc **`uvicorn main:app`** từ
thư mục dự án. Cài dependency chính vẫn bằng `pip install -r requirements.txt`.
Xem [tài liệu](docs/README.md) và [bộ skill](skills/README.md).

## Kiểu chữ cho video

Có 10 bộ font tiếng Việt theo chủ đề, tùy chọn tự chọn hoặc chọn cố định,
xem trước trên web. [Danh mục, mục đích và cách dùng](docs/TYPOGRAPHY.md).

## Nhịp dựng năng động

10 skill mới từ tham chiếu người dùng: nhấn ý, zoom có khoảng nghỉ, danh
sách hiện lần lượt và CTA đúng lời nói. Chọn Nhịp dựng trên giao diện;
[cách dùng, bằng chứng và giới hạn](docs/MOTION_SKILLS.md). Chưa fine-tune model.

## Duyệt tên và cache nhận dạng

Tên chuẩn được gợi ý trước khi nhận dạng. Có nút áp dụng tên vào bản nháp
để xem và lưu rõ ràng, không tự ghi đè phụ đề đã sửa. Cache mới gắn nguồn
và cấu hình. [Cách dùng và kiểm chứng Ollama thật](docs/RECOGNITION_REVIEW.md).
