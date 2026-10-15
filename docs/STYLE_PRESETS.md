# Phong cách dựng theo chủ đề

## Luồng sử dụng

Thêm video → chọn một thẻ phong cách → **Dựng video**. Nút dựng đặt ngay sau phần chọn phong cách và yêu cầu tùy chọn, không cần cuộn qua các thiết lập tài nguyên. Có thể thêm logo, tối đa 6 ảnh, nhạc nền và tên riêng. Cắt tiếng đệm là tùy chọn riêng, mặc định tắt.

| ID API | Phong cách | Quy tắc thực thi |
| --- | --- | --- |
| `explainer` | Giải thích · Năng động | Giữ pipeline cũ; nhịp dựng và chữ do các thiết lập hiện tại quyết định. |
| `inspirational` | Truyền cảm hứng · Cảm xúc | Gom ý dài hơn (mốc mục tiêu 9 giây, ranh giới câu từ 4,8 giây); chữ Lora khi chọn tự động; zoom tối đa 1,045; chuyển ảnh khoảng 0,23 giây; ít âm nhấn, màu tím than và vàng ấm. |
| `real_estate` | Bất động sản · Sang trọng | Ý ngắn hơn (mốc mục tiêu 5,5 giây, ranh giới câu từ 2,6 giây); chữ Noto Serif khi chọn tự động; zoom tối đa 1,025; ảnh người dùng toàn khung; chuyển ảnh khoảng 0,17 giây; màu xanh trầm và vàng nhạt. |

Đây là mốc chia theo lời nói, không phải ép mọi cảnh đúng số giây. Không thay đổi tốc độ phát, không cắt câu để đạt mốc. Giữ timestamp nguồn và ánh xạ sau bước cắt tiếng đệm; giữ toàn bộ timeline. Các nguồn dài vẫn chịu giới hạn số cảnh có sẵn.

## Tài nguyên và âm thanh

- Ảnh có từ khóa chỉ ghép khi khớp lời nói theo bộ ghép sẵn có; để trống ghép theo thứ tự. Không suy luận rằng một ảnh là đúng căn nhà chỉ từ việc người dùng chọn preset.
- Không có ảnh khớp trong preset Bất động sản: dùng footage gốc và báo rõ. Không lấy ảnh thư viện chung làm ảnh tài sản, tự dựng sơ đồ mặt bằng, giá, diện tích hay địa chỉ.
- Hướng dẫn thẩm mỹ được gửi riêng trong `editing_style`, không nối vào brief làm nguồn sự thật hoặc chữ hiển thị. Bộ quy tắc sau planner loại đồ họa chung khỏi hai preset mới và chỉ dùng cụm từ nguồn để nhấn ý.
- Không có file nhạc: không tự tạo hoặc tải nhạc. File nhạc được thêm vào mix sẵn có với sidechain ducking dưới tiếng nguồn, fade ở đầu/cuối; âm lượng cơ sở 0,10 (cảm hứng), 0,08 (bất động sản), 0,12 (giải thích). Nhạc ngắn kết thúc khi hết file và có cảnh báo; không tự lặp.
- “Không âm thanh” tắt nhạc/âm nhấn bổ sung, giữ lời nói gốc. “Không hiệu ứng” tắt zoom/chuyển động; “không chữ” tắt chữ/phụ đề. Chọn font cụ thể ưu tiên hơn font của preset. Hai preset mới dùng nhịp riêng nên ô nhịp dựng cũ bị vô hiệu hóa khi chọn chúng.

## Kiến trúc

`backend/style_presets.py` là danh mục và adapter thực thi. Giữ các bộ skill chung hiện có, không nhân bản pipeline và không nhập mã/skill của các repo bên ngoài trong thay đổi này. Các repo đã trao đổi là nguồn nghiên cứu kiến trúc; không tuyên bố đã tích hợp tất cả hoặc đã huấn luyện lại model. Không bổ sung HyperFrames/SeeCut hoặc dịch vụ API trả phí.

`MakeVideo.style_preset` được kiểm tra bằng danh sách Literal. Lựa chọn lưu trong job và kế hoạch, phục hồi khi mở lịch sử/tải lại trang. Các preset không trao đường dẫn, filter hay lệnh shell cho model.

Trình tự: nguồn/nhận dạng → cắt tiếng đệm nếu bật → chia ý theo preset → planner cùng skill chung → ghép tài nguyên → font → chuyển động chung → adapter preset → xác thực timeline → render → giải mã toàn bộ MP4 → kiểm tra thời lượng, tiếng nguồn và khung dọc 720×1280 → công bố kết quả.

Thiếu/lỗi Ollama vẫn theo cơ chế dự phòng hiện có, có nhãn **Dự phòng** và cảnh báo. Đây là dựng theo quy tắc, không được gọi là suy luận AI thành công. Whisper và Ollama thực vẫn phải được cài/tải model để chạy luồng AI trên video mới có lời nói. Việc cập nhật GitHub không tự cập nhật máy đang chạy ứng dụng.

## Kiểm tra lại

```bash
python -m pip install -r requirements/requirements-dev.txt
python -m pytest -q
node --check frontend/simple.js
node --check motion_engine/render_scene.js
```

Smoke check trình duyệt thực, với Chrome và Playwright cho Node đã cài:

```bash
# PLAYWRIGHT_MODULE có thể là đường dẫn tuyệt đối tới module Playwright.
CHROME_PATH=/path/to/chrome PLAYWRIGHT_MODULE=/path/to/playwright \
  python scripts/verify_style_presets.py --output-dir /tmp/style-preset-qa
```

Script tự tạo video test pattern, âm kiểm thử, ảnh nhà vẽ phục vụ kiểm thử và SRT nhập qua API; mở giao diện thật, chọn ảnh/nhạc, dựng hai phong cách, tải lại trang, kiểm tra mobile và MP4. Không dùng lời nói/video khách hàng, không mô phỏng ASR thành nhận dạng thật. Báo cáo ghi rõ `real_asr_tested=false` và `real_model_inference_tested=false`. Kiểm tra kỹ thuật không thay thế việc nghe/xem video thật để duyệt cảm xúc và độ phù hợp minh họa.
