# Bảy skill dựng video cơ bản

Đây là bộ hướng dẫn cho planner Ollama của dự án, không phải trọng số model
đã được fine-tune. Bảy skill được nạp mặc định trong `editing_skills.json`:

| Skill | Mục tiêu thẩm mỹ |
| --- | --- |
| Chữ gọn, có thứ bậc | Một tiêu đề chính ngắn, không nhồi nhiều lớp chữ; giữ tên riêng cùng dòng. |
| Phụ đề rõ, đúng lời | Giữ câu đã duyệt và thời gian engine; không đoán từ chưa chắc. |
| Zoom nhẹ có chủ đích | Ưu tiên đỉnh zoom 1.04–1.10 ở ý nhấn, có khoảng nghỉ; tôn trọng yêu cầu tắt hiệu ứng. |
| Minh họa đúng ý | Một ý rõ mỗi hình; ưu tiên ảnh người dùng phù hợp, sơ đồ đơn giản và người nói đủ lớn. |
| Thương hiệu nhất quán | Dùng đúng tên và logo dự án; giữ khoảng trống cho logo, tiêu đề và phụ đề. |
| Nhịp dựng tinh tế | Giữ người nói ở mở/kết; minh họa ở đoạn phù hợp; hiệu ứng âm thanh nhẹ, không lấn giọng. |

| Bỏ tiếng đệm, nối lời | Khi người dùng bật: engine cắt tiếng đệm đủ chắc, nối hình/tiếng và ánh xạ phụ đề; không tự cắt từ có nghĩa. |

[Cách bật và giới hạn cắt tiếng đệm](../docs/SPEECH_CLEANUP.md).

`learning_store.editor_skills()` đọc các rule bật, giới hạn độ dài và đưa vào
style guidance của lần lập kế hoạch tự động. Tối đa tám skill, tổng rule tối
đa 1.800 ký tự. File sai định dạng không làm hỏng pipeline; bộ quy tắc an
toàn sẵn có vẫn được dùng. Hướng dẫn không yêu cầu model xuất thêm trường.

Đổi `enabled` thành `false` để tắt một skill. Sửa `rule` để điều chỉnh hướng
dẫn; `name` là mô tả dành cho người đọc. Dùng câu ngắn và phù hợp với chức
năng renderer đang hỗ trợ. Các skill giữ framework và schema hiện có, không thêm dependency.
Skill tiếng đệm có thể rút ngắn timeline khi người dùng bật. Logo/font/bố cục thực tế vẫn do engine đảm nhiệm.

Yêu cầu hiện tại, lời nói và schema có ưu tiên hơn các mẫu phong cách.
Phản hồi được duyệt tiếp tục được lưu riêng; không tự đưa mọi góp ý thành
quy tắc chung. Khi Ollama không chạy, fallback vẫn dùng engine hiện có, chưa
được tuyên bố là áp dụng đầy đủ các skill hoặc góp ý tự do.

Cách dùng: cập nhật code, dựng video khác, xem kết quả, góp ý cụ thể rồi
bấm Duyệt phong cách hoặc Cần cải thiện. Đánh giá trên nhiều video trước
khi thay đổi rule dùng chung. Bộ skill này là điểm khởi đầu; chất lượng
model thật chưa được benchmark trong đợt bổ sung hướng dẫn này.

## Bộ chữ theo chủ đề

`typography.json` chứa 10 bộ font với mục đích riêng cho phụ đề, tiêu đề,
nhãn và thương hiệu. [Cách dùng và giấy phép](../docs/TYPOGRAPHY.md).

## 10 skill chuyển động mới

`motion_skills.json` được nạp có điều kiện khi chọn Nhịp dựng năng động.
Kết hợp bảy skill cơ bản; không gửi cả thư viện không giới hạn cho model.
[Điều kiện, khả năng renderer và giới hạn](../docs/MOTION_SKILLS.md).
