# Auto Video Editor (DANAVA)

Hệ thống dựng video tự động từ nền tảng Python FastAPI và Vanilla JS.

## Tính năng (Đã hoàn thành Sprints 1-7)

- **Upload & Quản lý**: Kéo thả MP4, đọc metadata bằng FFprobe.
- **Timeline & Trim**: Cắt gọt clip, lồng overlay.
- **Subtitles**: Tích hợp mô hình Whisper (Nhận dạng giọng nói) để xuất phụ đề và tự động render burn-in phụ đề vào video gốc qua FFmpeg SRT.
- **Assets**: Upload và chèn Ảnh/Video minh họa vào Timeline (Picture-in-picture, Overlay).
- **Auto Edit**: Nút dựng tự động dựa trên tài nguyên đang có.
- **Render Worker**: Chạy ngầm tiến trình ffmpeg phức tạp (gộp nhiều filter `overlay`, `subtitles`).

## Cách chạy

1. Cài đặt Python (khuyên dùng Python 3.10+).
2. Tạo venv và cài phụ thuộc:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   pip install openai-whisper  # nếu muốn dùng auto subtitle
   ```
3. Cài đặt `ffmpeg` và `ffprobe` (phải có trong PATH của hệ thống).
4. Khởi động Backend:
   ```bash
   python main.py
   ```
5. Truy cập: `http://127.0.0.1:8000/frontend/index.html`

## Ghi chú
- Nếu quá trình `pip install openai-whisper` gặp khó khăn, bạn vẫn có thể sử dụng các chức năng Upload, Trim và Overlay bình thường (chỉ là nút Auto Transcribe sẽ báo lỗi).
- Timeline được thiết kế kéo/thả đơn giản nhất qua việc click và chỉnh sửa thông số `Start`, `Duration`.
