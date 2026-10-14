# Bộ skill dựng năng động theo tham chiếu

Video người dùng gửi ngày 14/10/2026 dài 168,149 giây, 640×360, khoảng
29,97 fps. Đã xem 35 khung trải đều và xem thêm các đoạn chuyển cảnh. Tại
ngưỡng scene-score > 0,25 có 20 thay đổi hình lớn; một hiệu ứng chớp/xoay có
thể tạo nhiều lần phát hiện, nên con số này không phải số cú cắt thật.

Các quan sát: 0–4 giây mở bằng chữ lớn; 5–15 giây xen khung người nói;
16–21 giây hiện các ý lần lượt; 30–46 giây nhấn cụm chữ; 75–95 giây thẻ
minh họa/danh sách; 102–110 và 134–138 giây footage bổ sung; 120–151 giây
nhấn số liệu/lời kêu gọi; 158–168 giây thẻ kết. Chỉ lưu đặc tính dựng và
SHA-256 trong bộ skill; không đưa video, thương hiệu, giá, lời thoại hoặc
timeline của tham chiếu vào planner cho video khác.

## 10 skill mới

| Skill | Mục đích | Điều kiện / thực thi |
| --- | --- | --- |
| Mở đầu theo nội dung | Đưa ý chính lên sớm | Planner chọn ý từ lời nói; không chèn intro im lặng hay cắt giọng. |
| Nhấn từ khóa | Tạo thứ bậc chữ | ASS/Chrome nhấn tối đa hai từ cuối của cụm có trong lời nói, hiện ngắn. |
| Zoom vào rồi trả khung | Có nhịp và khoảng nghỉ | Adapter xen cảnh camera tĩnh và đường zoom sin² 1 → 1,065 → 1. |
| Danh sách hiện lần lượt | Giải thích dễ theo dõi | 2–5 nhãn đúng nội dung, đủ thời gian đọc; Chrome reveal có khoảng nghỉ cuối. |
| Minh họa bằng tài nguyên thật | Liên quan đến nội dung | Dùng ảnh/footage dự án khi có; không lấy footage mẫu làm ảnh minh họa cho mọi video. |
| Chuyển động vào cảnh mềm | Hạn chế cảm giác giật | Slide/fade ngắn, không thêm flash/xoay, không xê dịch audio hoặc tổng thời lượng. |
| Số liệu đúng lời | Giữ độ tin cậy | Chỉ nhấn số liệu có trong lời nói; không tạo giá gạch ngang hay phần trăm giảm giá. |
| Kết video đúng yêu cầu | CTA có căn cứ | Trích đoạn hành động ở lời kết; không tự tạo link, khan hiếm hay đếm ngược. |
| Khoảng nghỉ thị giác | Không nhồi hiệu ứng | Tiêu đề camera tối đa 2,6 giây, giữ phụ đề và các vùng chữ riêng. |
| Âm thanh nhấn nhẹ | Giữ giọng nói chủ đạo | Âm lượng SFX cảnh tối đa 0,07, tôn trọng yêu cầu tắt hiệu ứng/âm thanh. |

Skill là hướng dẫn có điều kiện và adapter renderer, **không phải fine-tune
trọng số**. Sáu skill cơ bản giữ nguyên. Bộ mới trong
`skills/motion_skills.json` có 10 rule, tổng 1.171 ký tự, chọn theo nguồn
hiện tại và preset. Không tăng số trường AI phải sinh, không tăng timeout,
không thêm dependency production. Một số skill như chọn hook/b-roll còn
phụ thuộc quyết định planner và tài nguyên có sẵn.

## Sử dụng

Giao diện chọn **Nhịp dựng → Năng động theo mẫu mới** cho video mới.
**Tinh gọn theo mẫu cũ** giữ hành vi cũ. Nút tạo, hủy, lịch sử và tải MP4
không thay đổi. Lựa chọn khôi phục khi tải lại trang. API cũ mặc định
`motion_style: clean`; khách mới có thể gửi `dynamic_explainer` trong
`POST /api/projects/{id}/make-video` hoặc `/auto-edit`.

Plan lưu `motion_style` và quyết định `motion` theo từng cảnh. Trường
`source: reference_rules` thể hiện engine áp dụng quy tắc, không giả là AI.
`GET /api/learning` liệt kê các skill chuyển động có sẵn; từng plan cho biết
các skill kích hoạt. Duyệt phong cách lưu preset/font dưới dạng thông tin
trừu tượng để planner tham khảo lần sau, không lưu lại lời thoại làm mẫu.

Khi Ollama lỗi, dựng dự phòng vẫn có nhấn chữ/zoom/thẻ phù hợp. Danh sách
mới trong fallback chỉ trích khi lời nói có đánh dấu liệt kê rõ, word confidence
đủ hoặc phụ đề đã sửa; không ép mọi dấu phẩy thành một quy trình. Ảnh đã
chọn không bị thay bằng danh sách. Nội dung không chắc chắn không được
phóng thành tuyên bố mới.

## Giới hạn thực tế

- Không tạo góc máy thứ hai khi chỉ có một nguồn; zoom không được gọi là
  quay đa góc. Chưa thêm chuyển cảnh xoay/flash hay thẻ giá/CTA đếm ngược.
- Không tự dựng ra footage sự kiện hoặc ảnh sản phẩm thiếu trong asset.
- Font, chữ và hình đã dính sẵn vào nguồn không thể đổi sạch bằng pipeline
  hiện tại. Ưu tiên video gốc chưa có chữ.
- Chưa nhận diện khuôn mặt để xác định safe area theo từng người. Dùng
  safe area hiện có và zoom nhẹ; cần xem lại framing nguồn đặc biệt.
- Chỉ thông tin kiểu dựng được đưa vào style memory. Không tuyên bố đã
  train lại Ollama hoặc đạt chất lượng tương đương editor tham chiếu.

## Kiểm chứng

Xem `verification/MOTION_VERIFICATION.json`. Test bao phủ chữ đúng nguồn,
CTA/số liệu không bịa, tắt hiệu ứng, không phá phụ đề/timeline, danh sách
có điều kiện, lặp lại không tích lũy zoom, renderer Chrome thực và chuyển
preset trên giao diện. Nhánh nhận guidance của AI dùng phản hồi kiểm soát;
Ollama không khả dụng trên máy kiểm thử, nên chất lượng kế hoạch từ model
thật trong lần thay đổi này chưa được đánh giá.

Kết quả thực tế: 138 test cũ, 11 test motion mới và 62 test hồi quy cuối
đã qua. Hai MP4 được decode toàn bộ: 37,3 giây (138,416 giây render) và
32 giây (90,503 giây render), đều có audio. Phần nhận dạng được đo riêng
rồi dùng lại đúng nguồn trong dự án; `recognition_seconds=0` trong job
dựng không có nghĩa là Whisper nhận dạng tức thì. Nguồn marketing thử
nghiệm là trích đoạn/crop 32 giây, không phải chạy toàn bộ file 115 giây.
Các video thử còn từ ASR cần duyệt; không thay thế bản phụ đề đã duyệt trước đó.
