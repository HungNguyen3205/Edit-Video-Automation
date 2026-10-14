# Bỏ tiếng đệm và nối lời

Bật **Bỏ tiếng đệm “ờ, ừm”** trước khi bấm Tạo video, hoặc nhập:
“Bỏ tiếng đệm ờ, ừm, giữ nguyên lời nói có nghĩa và nối lời tự nhiên”.
API `/make-video` nhận `remove_fillers: true`; mặc định false để dự án cũ
vẫn giữ đủ nguồn. Yêu cầu “không cắt ờ” hoặc “giữ tiếng đệm” có ưu tiên
hơn tùy chọn. Video gốc và các bản xuất trước vẫn được giữ.

Đây là skill có thực thi bằng engine, không phải fine-tune model. Ollama
không quyết định timestamp. `backend/speech_cleanup.py` nhận word timestamps
Whisper, chọn tiếng đệm độc lập đủ chắc, tách source clips bằng schema hiện
có và giữ phụ đề ở source-time. Adapter storyboard giữ các phụ đề này;
engine ánh xạ lại theo phần nguồn còn lại. FFmpeg thêm ramp âm lượng 6 ms
ở điểm nối để hạn chế tiếng click, không trộn hai câu hay thay đổi tốc độ.
Không hứa biến mọi cú nhảy hình thành một góc máy liền mạch.

## Quy tắc thận trọng

- Chỉ xét `ờ`, `ờm`, `ừm`, `um`, `umm`, `uh`, `erm`, `hmm` có confidence
  từ 0,65, dài 0,18–1,5 giây và không lấn từ lân cận. Không đổi model ASR.
- Không tự xóa `à`, `ừ`, `ơ`, `òm`: có thể là từ có nghĩa. Giữ từ được trích
  dẫn, sau “từ/chữ/tiếng”, hoặc trước “là”. Giữ tiếng nhận dạng chưa chắc.
- Điểm cắt khớp frame, có khoảng đệm nhỏ, mỗi đoạn giữ tối thiểu 80 ms;
  tối đa 40 tiếng đệm và 25% timeline, phải còn lời nói có nghĩa.
- Không tự rút gọn khoảng nghỉ, hơi thở, từ lặp hoặc câu có nội dung bằng quy tắc
  này. Hai điểm cắt tiếng đệm cách nhau dưới 80 ms chỉ được gộp khi
  không có từ có nghĩa ở giữa. Không tăng timeout, không thêm thư viện/model production.
- Nếu Whisper không ghi nhận tiếng đệm hoặc không có timestamp từng từ,
  giữ nguồn và báo rõ; không cắt dựa trên phụ đề theo câu.
- Phụ đề sửa tay được ưu tiên. Chỉ dùng lại điểm cắt đã xác nhận trên cùng
  nguồn/ASR; nếu người dùng khôi phục chữ tiếng đệm trong câu đã duyệt thì
  thu hồi điểm cắt đó. Dự án có phụ đề sửa tay nhưng chưa có điểm cắt xác
  nhận sẽ giữ nguồn; không ép căn chỉnh chữ sửa tay vào âm thanh khác.

Metadata `speech_cleanup` lưu phương pháp, source fingerprint, số lần cắt,
số giây bỏ, điểm cắt và ứng viên cần nghe lại. Giao diện báo kết quả thật.
Metadata này do server quản lý, không nhận điểm cắt tự khai từ `/edit_plan`.
Cache nhận dạng vẫn gắn nguồn/cấu hình; đổi tùy chọn không chạy lại ASR
không cần thiết. Mỗi lần tạo tự động bắt đầu từ nguồn gốc để không cắt dồn.

Kiểm thử: `python -m pytest -q tests/test_speech_cleanup.py`.
Các timestamp fixture dùng kiểm thử cắt/render có kiểm soát, không được
coi là kết quả nhận dạng thật. Xem thêm báo cáo trong `docs/verification/`.
