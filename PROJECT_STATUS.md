# PROJECT STATUS

## Sprint hiện tại
**Sprint 7 — ỔN ĐỊNH, HIỆU NĂNG VÀ BÀN GIAO (HOÀN TẤT MVP)**

## Chức năng hoàn thành
- **Sprint 1 (Nền tảng):** API Upload MP4, đọc `ffprobe`, `render_task` với `ffmpeg`.
- **Sprint 2 (Timeline):** JSON Schema `edit_plan`, giao diện chỉnh sửa thời lượng Clip.
- **Sprint 3 (Phụ đề):** Tích hợp Whisper, tạo file SRT tự động, thêm tab `Subtitles`, burn subtitle qua `filter_complex`.
- **Sprint 4 (Nhấn mạnh):** Cấu trúc Auto-Edit chèn keyframe overlay cơ bản.
- **Sprint 5 (Lồng Ảnh/Video):** Tab `Assets`, Timeline hỗ trợ nhiều Track (`track-main` và `track-overlay`), backend render ghép đa input.
- **Sprint 6 (Tự động):** Nút Auto Edit tự động sắp xếp tài nguyên phụ vào clip.
- **Sprint 7 (Bàn giao):** File README.md hướng dẫn cài đặt, phân tách kiến trúc rõ ràng Backend/Frontend theo đúng yêu cầu không Database, dễ copy.

## Kiểm tra đã chạy
- Giao diện HTML/JS hoạt động chuẩn, các tab chuyển đổi mượt mà.
- API Upload và Save Edit Plan thành công.
- Background Tasks (Transcribe & Render) được thiết lập không block server chính.

## Lỗi và giới hạn
- Model `whisper-tiny` có thể cài đặt chậm tuỳ cấu hình máy.
- Giao diện Editor hiện tại ưu tiên nhập số (Start, Duration) hơn là kéo thả phức tạp bằng JS do giới hạn của Vanilla JS trong MVP. Cần bổ sung thư viện drag/drop nếu muốn kéo mượt.

## Bước tiếp theo (Ngoài phạm vi Sprints)
- Thêm Preview thực tế bằng WebGL/Canvas trên Frontend để mô phỏng chính xác vị trí ảnh lồng/chữ mà không cần Render MP4.
- Hỗ trợ chọn điểm neo (Anchor) linh hoạt cho hiệu ứng Zoom.
