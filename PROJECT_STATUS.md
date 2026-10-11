# Trạng thái DANAVA Video Studio — mẫu đã duyệt

## Đã triển khai

- Renderer dùng chung phong cách mẫu được duyệt: 9:16, thẻ trắng, teal/navy, Barlow Condensed và Inter. Bản xem trước 360×640 giữ cùng bố cục bản xuất 720×1280.
- AI phải tạo storyboard đầy đủ theo prompt/transcript; không dùng luân phiên cố định khi chọn explainer_ref. Cảnh camera có headline/badge phía trên; graphics có chat/process/network, so sánh, số liệu, các bước, CTA, PIP và B-roll từ tài nguyên dự án.
- Dữ liệu minh họa và nội dung do storyboard cung cấp. Không gắn tên trợ lý, thông tin liên hệ hay dữ liệu bán hàng của video tham chiếu vào mọi nguồn.
- Giữ toàn bộ nội dung thực sự kiểm tra đủ timeline, thứ tự và không lặp đoạn. Storyboard phải đủ độ dài, không chồng cảnh; tự ánh xạ nguồn qua ranh giới cut. Kiểm tra file từng cảnh và độ dài trước khi xuất; ranh giới lượng tử hóa theo frame.
- Chữ, minh họa tải lên, zoom keyframe, SFX theo cảnh, nhạc tải lên/ducking đều đến renderer. SFX không át giọng; không có nhạc tải lên thì không tự chèn nhạc.
- CPU int8 faster-whisper là tùy chọn; vẫn hỗ trợ openai-whisper. Nhận dạng có timestamp từng từ; các từ/phụ đề theo đúng đoạn giữ lại. Tên riêng và từ nhận dạng sai cần xem/sửa trước khi đăng.
- UI có nút Dùng mẫu đã duyệt, dòng thương hiệu tùy chọn và khôi phục phong cách của bản đã lưu. Xuất lại giữ storyboard hiện tại; chạy AI lại lập storyboard mới.
- Phát hiện Node/Chrome trước khi render; CHROME_PATH và đường dẫn phổ biến Windows/Linux/macOS. Hủy dựng storyboard dừng nhóm process và có tiến độ theo cảnh.

## Đã kiểm tra

- 36 tests pass với FFmpeg và Chromium thật: giữ giọng, SFX, B-roll, preview, ánh xạ source/caption, literal text, repair schema, duration policy và hủy process. Test model dùng dữ liệu/phản hồi kiểm soát.
- node --check frontend/app.js và motion_engine/render_scene.js; git diff --check đều qua.
- Browser thực: mở dự án, bấm Dùng mẫu đã duyệt, xác nhận prompt/style/policy/planner, không có pageerror; đã xem screenshot giao diện.
- API upload → nhận dạng faster-whisper small CPU thật → director/validation → renderer → MP4 37,3 giây, 720×1280, audio. Kiểm tra decode toàn bộ file thành công và xem các cảnh đầu/cutaway. Planner trong bài thử này dùng phản hồi có kiểm soát, không phải Ollama inference thật.

## Giới hạn

Chưa kiểm chứng chất lượng suy luận bằng model Ollama thật hay model thị giác trong môi trường phát triển. Chất lượng chọn cảnh phụ thuộc model/transcript; engine không cam kết mọi prompt đều đạt mẫu ngay lần đầu. Đồ họa tạo tại máy là minh họa khái niệm; chưa tự tìm stock, tạo ảnh photorealistic/nhạc, theo dõi khuôn mặt hoặc speed ramp. Một worker, lưu dữ liệu cục bộ; chưa dành cho multi-user/public hosting. Xem APPROVED_STYLE.md để cài và dùng mẫu.
