# DANAVA Video Studio — luồng một nút (12/10/2026)

## Đã hoàn thành

- Trang chính: một vùng chọn/thả video, một prompt tùy chọn, nút Tạo video của tôi, video kết quả và tải MP4. Style/nhận dạng/thời lượng/xuất được chọn ở backend. Giao diện thủ công cũ nằm ở /frontend/advanced.html.
- /make-video mặc định xuất toàn bộ nguồn bằng phong cách mẫu, không yêu cầu dựng preview rồi xuất lần nữa. Dựng lại từ video và bản nhận dạng gốc, tránh tích lũy cắt hoặc sửa phụ đề qua nhiều lần.
- Model chọn nội dung/khái niệm theo lời nói. Schema khóa số cảnh và mã cảnh. Engine hoàn thiện bố cục từ khái niệm AI cung cấp theo độ khớp với lời thoại, không theo chu kỳ thời gian. Không tạo kế hoạch thay thế khi Ollama/model thiếu hoặc lỗi.
- Kiểm tra nhãn minh họa dựa trên từ vựng nguồn/prompt và nhãn trung tính. Từ chối lời khẳng định không có căn cứ như AI đầu tiên/tối ưu thuật toán. Cảnh lỗi được sửa riêng, giữ cảnh hợp lệ.
- Mức zoom 1.4 được giới hạn về 1.2. Subtitles có thể tắt theo yêu cầu. Sửa phụ đề quá khác nguồn bị thay bằng phụ đề nhận dạng và ghi cảnh báo; không tự khai báo timestamp từ khi chỉ có timestamp đoạn.
- Giữ các kiểm tra thời lượng, FFprobe, từng cảnh, caption/audio, SFX và renderer của phiên bản trước.

## Bằng chứng kiểm tra

- 51 tests passed với FFmpeg và Chromium thật; bao gồm API một nút xuất MP4, giữ nguồn, hủy, duration, caption, SFX, B-roll, khôi phục phụ đề nguồn, sửa cảnh riêng và bố cục từ khái niệm AI. Kiểm thử hợp đồng model dùng phản hồi kiểm soát.
- Browser thật: upload -> nhập prompt -> tạo -> tải MP4; refresh giữ kết quả; không pageerror; mobile 390px không tràn ngang. Browser test dùng nhận dạng/model fixture để kiểm tra luồng UI.
- Chạy Qwen3-4B-Q4_K_M thật qua Ollama, think=false; nhận được đủ sáu cảnh. Bản xuất cuối 720x1280, có audio, đủ 37.3 giây; giải mã toàn bộ MP4 không lỗi. Nguồn, timeline, storyboard và MP4 đều 37.3 giây.
- Lần kiểm tra cuối dùng transcript/timestamp đã lưu từ faster-whisper small CPU nhận dạng thật trên đúng demo.mp4. Không biên tập storyboard hoặc dùng model trả lời giả cho lần chọn cảnh này. Engine hoàn thiện một cảnh camera thành PIP hội thoại từ khái niệm model cung cấp; model cũng tự chọn PIP minh họa thử nghiệm. SFX pop/chime từ kế hoạch được trộn vào video.
- Đã xem khung hình ở 2.5, 10, 16, 23, 28, 34 giây: chữ, người nói và minh họa hiển thị; không ảnh mất hoặc khung đen trong các mốc kiểm tra. Đây là kiểm tra mẫu khung hình, không khẳng định đã kiểm tra thị giác từng frame.

## Chưa đạt chất lượng tuyệt đối

Nhận dạng small vẫn sai “Veroi” và “chết” ở một số câu của demo. Code không tự đoán một từ thay thế chưa chắc đúng chỉ để làm đẹp kết quả. Vì vậy bản thử chứng minh luồng tự dựng, thời lượng và bố cục hoạt động, chưa chứng minh phụ đề chính xác tuyệt đối hay mọi video đạt chất lượng như bản biên tập tay đã duyệt. Cần xem/nghe phụ đề trước khi đăng; có thể sửa SRT ở trang nâng cao. Tên riêng cung cấp trong prompt giúp sửa cách viết, không đảm bảo sửa mọi lỗi nhận dạng.

Suy luận dài/nhanh với model nhỏ đã có các lần trả thiếu cảnh, thẻ rỗng hoặc thêm ý không có trong nguồn; những kế hoạch đó bị từ chối. Chạy nhiều tiến trình model cùng lúc trong môi trường thử hạn chế RAM gây unexpected EOF; bản thành công chạy một model. Không coi JSON hợp lệ là bằng chứng dựng đẹp. Chất lượng video khác/chủ đề khác vẫn cần kiểm tra thêm.

Chưa tự tìm stock Internet, tạo ảnh photorealistic/nhạc, theo dõi mặt hoặc huấn luyện model. Thư viện hình là minh họa khái niệm; nguồn audio luôn là video gốc. Một worker; chưa dành cho public hosting/multi-user.

## Chạy

Theo APPROVED_STYLE.md. Dừng server cũ, git pull origin main, cài requirements/Node dependencies nếu thiếu, python main.py; mở http://127.0.0.1:8000 và tải lại trang.
