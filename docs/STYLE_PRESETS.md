# Phong cách dựng theo chủ đề

## Luồng sử dụng

Giao diện chính có đúng 3 ô: **Thêm video → Chọn phong cách → Xuất video kết quả**. Không còn prompt, logo, nhạc, chọn font, bộ sửa phụ đề hay phản hồi trên luồng chính. Bấm **Dựng & xuất video**, xem và tải MP4 ngay trong ô thứ ba. API/trang nâng cao giữ chức năng chi tiết để tương thích.

| ID API | Phong cách | Quy tắc thực thi |
| --- | --- | --- |
| `explainer` | Giải thích · Năng động | Giữ bộ dựng giải thích chung; luồng 3 ô bật nhịp năng động, chữ nhấn vàng–xanh và phụ đề theo cụm. |
| `inspirational` | Truyền cảm hứng · Cảm xúc | Gom ý dài hơn (mốc mục tiêu 7 giây, ranh giới câu từ 4,8 giây); chữ Montserrat khi chọn tự động; nhịp trình bày khoảng 2,4 giây; zoom tới 1,20; chữ neon cỡ 64, 3 từ/cụm; ảnh thư viện khớp lời nói; tiếng pop/whoosh ở đầu cảnh. |
| `real_estate` | Bất động sản · Sang trọng | Ý ngắn hơn (mốc mục tiêu 5,5 giây, ranh giới câu từ 2,6 giây); chữ Be Vietnam Pro khi chọn tự động; zoom tối đa 1,07; ảnh người dùng toàn khung; chuyển ảnh khoảng 0,17 giây; màu xanh trầm và vàng nhạt. |

Đây là mốc chia theo lời nói, không phải ép mọi cảnh đúng số giây. Không thay đổi tốc độ phát, không cắt câu để đạt mốc. Giữ timestamp nguồn và ánh xạ sau bước cắt tiếng đệm; giữ toàn bộ timeline. Các nguồn dài vẫn chịu giới hạn số cảnh có sẵn.

## Tài nguyên và âm thanh

- Ảnh có từ khóa chỉ ghép khi khớp lời nói theo bộ ghép sẵn có; để trống ghép theo thứ tự. Không suy luận rằng một ảnh là đúng căn nhà chỉ từ việc người dùng chọn preset.
- Không có ảnh bổ sung: dùng footage gốc và có thể chèn một cảnh ngắn 1,2–1,4 giây từ chính khung hình nguồn, ghi nhãn KHUNG HÌNH TỪ VIDEO GỐC. Không dùng cảnh đóng băng cho toàn bộ đoạn nói. Không lấy ảnh thư viện chung làm ảnh tài sản, tự dựng sơ đồ mặt bằng, giá, diện tích hay địa chỉ.
- Hướng dẫn thẩm mỹ được gửi riêng trong `editing_style`, không nối vào brief làm nguồn sự thật hoặc chữ hiển thị. Bộ quy tắc sau planner giữ ảnh minh họa liên quan cho Truyền cảm hứng, loại đồ họa chung khỏi Bất động sản và chỉ dùng cụm từ nguồn để nhấn ý.
- Không có file nhạc: không tự tạo hoặc tải nhạc. File nhạc được thêm vào mix sẵn có với sidechain ducking dưới tiếng nguồn, fade ở đầu/cuối; âm lượng cơ sở 0,10 (cảm hứng), 0,08 (bất động sản), 0,12 (giải thích). Nhạc ngắn kết thúc khi hết file và có cảnh báo; không tự lặp.
- “Không âm thanh” tắt nhạc/âm nhấn bổ sung, giữ lời nói gốc. “Không hiệu ứng” tắt zoom/chuyển động; “không chữ” tắt chữ/phụ đề. Chọn font cụ thể ưu tiên hơn font của preset. Các lựa chọn chi tiết này dùng qua API/trang nâng cao, không hiện trên giao diện 3 ô.

## Kiến trúc

`backend/style_presets.py` là danh mục và adapter thực thi. Giữ các bộ skill chung hiện có, không nhân bản pipeline và không nhập mã/skill của các repo bên ngoài trong thay đổi này. Các repo đã trao đổi là nguồn nghiên cứu kiến trúc; không tuyên bố đã tích hợp tất cả hoặc đã huấn luyện lại model. Không bổ sung HyperFrames/SeeCut hoặc dịch vụ API trả phí.

`MakeVideo.style_preset` được kiểm tra bằng danh sách Literal. Lựa chọn lưu trong job và kế hoạch, phục hồi khi mở lịch sử/tải lại trang. Các preset không trao đường dẫn, filter hay lệnh shell cho model.

Trình tự: nguồn/nhận dạng → cắt tiếng đệm nếu bật → chia ý theo preset → planner cùng skill chung → ghép tài nguyên → font → chuyển động chung → adapter preset → xác thực timeline → render → giải mã toàn bộ MP4 → kiểm tra thời lượng, tiếng nguồn và khung dọc 720×1280 → công bố kết quả.

Thiếu/lỗi Ollama vẫn theo cơ chế dự phòng hiện có, có nhãn **Dựng theo quy tắc (AI chưa hoàn thành)** và cảnh báo. Đây là dựng theo quy tắc, không được gọi là suy luận AI thành công. Whisper và Ollama thực vẫn phải được cài/tải model để chạy luồng AI trên video mới có lời nói. Việc cập nhật GitHub không tự cập nhật máy đang chạy ứng dụng.

## Kiểm tra lại

```bash
python -m pip install -r requirements/requirements-dev.txt
python -m pytest -q
node --check frontend/studio.js
node --check motion_engine/render_scene.js
```

Smoke check trình duyệt thực, với Chrome và Playwright cho Node đã cài:

```bash
# PLAYWRIGHT_MODULE có thể là đường dẫn tuyệt đối tới module Playwright.
CHROME_PATH=/path/to/chrome PLAYWRIGHT_MODULE=/path/to/playwright \
  python scripts/verify_three_panel_studio.py --output-dir /tmp/style-preset-qa
```

Script kiểm tra tải video không tiếng qua giao diện thật, sau đó dựng cùng một nguồn có âm và SRT nhập qua API ở cả ba phong cách. Không thêm ảnh/nhạc. Kiểm tra 3 ô, không còn form thừa, khôi phục sau tải lại, mobile, cảnh lấy từ nguồn, hướng zoom, pixel phụ đề màu, thời lượng, giải mã MP4 và tín hiệu âm thanh nguồn. Không dùng lời nói/video khách hàng, không mô phỏng ASR thành nhận dạng thật. Báo cáo ghi rõ `real_asr_tested=false` và `real_model_inference_tested=false`. Kiểm tra kỹ thuật không thay thế việc nghe/xem video thật để duyệt cảm xúc và độ phù hợp minh họa.

## Thiết kế phụ đề và zoom phiên bản 2

Phụ đề hiển thị 3 từ/cụm ở Truyền cảm hứng và 6 từ/cụm ở Bất động sản, giữ tên riêng nhiều từ khi đã có thông tin. Từ có căn chỉnh thực được nhấn màu theo timestamp; nguồn chỉ có SRT dùng nhấn theo cụm. Chữ được đo theo font cục bộ, giảm cỡ khi cần để giữ vùng an toàn. Chữ nguồn được escape riêng, không được chèn mã ASS. Zoom có hướng `in`/`out` dùng easing cosine; hướng mặc định `breath` của dự án cũ vẫn giữ. Cảnh khung hình nguồn được lấy sau khi ánh xạ source-time qua các điểm cắt.

Giao diện 3 ô không phát lại file của phong cách khác khi vừa đổi lựa chọn. Bản dựng cũ (`style_preset.version < 3`) được yêu cầu dựng lại; không coi đó là thành phẩm mới.

Bằng chứng kiểm tra phiên bản 3 ô: [THREE_PANEL_STUDIO_VERIFICATION.json](verification/THREE_PANEL_STUDIO_VERIFICATION.json).

## Phiên bản 3: Truyền cảm hứng mạnh

Giữ ảnh thư viện mà phiên bản trước xóa tại bước preset. Mỗi nhịp thứ ba có thể chọn ảnh offline theo từ khóa trong lời nói; hiện thư viện có hai chủ đề trợ lý AI và chiến lược thương hiệu. Nội dung khác cần ảnh người dùng hoặc mở rộng thư viện; không khẳng định tự sinh ảnh theo mọi chủ đề. Nhịp dựng chia phần hình, giữ nguyên giọng nói và timestamp. Giới hạn 200 cảnh và 100 track âm thanh vẫn được tôn trọng. Giao diện giữ đúng 3 ô.
