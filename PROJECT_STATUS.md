# Trạng thái DANAVA Video Studio

## Đã triển khai

- AI Director gọi model Ollama tại máy bằng JSON schema; nhận prompt tiếng Việt, transcript, clip/tài nguyên và mốc scene/silence. Có gửi ảnh mẫu khi cấu hình model thị giác.
- AI chọn đoạn giữ/thứ tự và điểm cắt, zoom/chữ/minh họa/âm thanh; kế hoạch không hợp lệ được sửa một lần rồi báo lỗi. Không fallback thành quy tắc khi người dùng chọn AI.
- Compiler dựng MP4 thật; phụ đề và chỉnh sửa thủ công được ánh xạ lại sau cắt. Nhạc tải lên có fade/lặp, ducking theo lời nói, limiter; whoosh/impact/chime tổng hợp tại máy.
- UI có prompt/gợi ý, trạng thái model, nhạc nền, dựng thử và giải thích quyết định. Chế độ quy tắc được ghi rõ.

## Kết quả kiểm tra

- 21 tests qua, gồm kiểm thử FFmpeg thực tế và HTTP streaming với máy chủ Ollama giả lập.
- `node --check frontend/app.js` qua. DOM interaction test qua: mở dự án, gợi ý prompt, báo thiếu model, chuyển chế độ, xuất thật và link tải; không lỗi JS. Chưa kiểm tra layout bằng trình duyệt do không tải được Chromium trong môi trường này.
- Không có Ollama/model/Whisper cài trong môi trường kiểm thử; chưa kiểm chứng chất lượng quyết định với model thật hoặc nhận dạng giọng nói thật. Kiểm thử HTTP/schema dùng response kiểm soát và không được coi là AI inference thật.

## Giới hạn còn lại

- Mặc định hiểu nội dung qua transcript, chưa nhìn hình. Thị giác tùy chọn chỉ lấy tối đa 8 ảnh mẫu và chưa kiểm thử model thật.
- Phân tích scene/silence tối đa 120s mỗi clip. Không tạo nhạc nền, ảnh hay stock tự động. Không speed ramp/face tracking/chuyển cảnh phức tạp.
- Chạy AI lại dùng timeline hiện tại; xem bản thử để kiểm tra ý nghĩa lời nói sau cắt. Không có undo phiên dựng tự động.
- Một worker, lưu file cục bộ, chưa dành cho nhiều người dùng/public hosting.
