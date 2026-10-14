# Ảnh minh họa và chuyển cảnh theo mẫu

## Đối chiếu mẫu

Mẫu người dùng gửi dài 168,149 giây, 640×360: xen người nói với ảnh/cảnh
chèn, tiêu đề lớn màu trắng/vàng, bảng ý chính và nhấn âm thanh. Đây là mục
tiêu biên tập, không phải giấy phép lấy người, cảnh, nhãn hàng hay giá trong
mẫu ghép sang video khác. Bản này ưu tiên phần còn thiếu: ảnh thật trong
khung hình và chuyển mềm giữa các bố cục, giữ nguyên giọng/thời lượng nguồn.
Không khẳng định đã đạt toàn bộ chất lượng dựng tay của mẫu.

## Đã triển khai

- `backend/visual_library.py`: kho ảnh tại máy với manifest trong
  `skills/visual_library.json`. Bản đầu có hai ảnh được tạo riêng bằng
  imagegen: trợ lý AI khái niệm và nhóm nhân vật hư cấu lập chiến lược hình
  ảnh/thương hiệu. Không phải ảnh khách hàng thật hoặc screenshot sản phẩm.
  Ảnh WebP tổng cộng khoảng 230 KB, không tải model tạo ảnh/API khi render.
- Chọn theo cụm từ của cảnh hiện tại, không dựa tên video mẫu hoặc tên dự án.
  Không khớp AI bên trong từ hai. Giữ mở/đóng bằng người nói, ưu tiên ảnh
  người dùng, tối đa hai ảnh thư viện mỗi video, có khoảng nghỉ giữa các ảnh.
  Cảnh dài được tách thành một nhịp ảnh ngắn và camera; không cắt lời nói.
- `motion_engine/render_scene.js`: ảnh toàn khung với nền tối chuyển sắc,
  tiêu đề đúng lời, ảnh chuyển động nhẹ; xen bố cục ảnh và người nói phía
  dưới. Chế độ không hiệu ứng giữ ảnh đứng; không chữ bỏ cả nhãn ảnh.
- Ảnh người dùng trong chế độ năng động cũng xen toàn khung/PIP. Ảnh không
  bị thay bằng danh sách chữ. Logo và phụ đề vẫn đi qua renderer hiện có.
- `backend/scene_transitions.py`: dissolve ngắn ở ranh giới thay đổi bố cục.
  Chỉ kéo dài hình cuối của cảnh đi đúng số frame dissolve, rồi dùng phần
  kéo dài ấy để overlap. Cảnh đến vẫn bắt đầu tại timestamp cũ; tổng frame
  không bị trừ. Tiếng gốc dựng riêng, không chồng/cắt theo dissolve.
  Camera liên tiếp được remux thành nhóm để hạn chế số decoder/chi phí RAM.
- Dùng thời lượng cảnh sau khi cắt preview, tránh cộng lại độ dài cảnh đầy
  đủ vào bản 12 giây. Hủy vẫn đi qua worker/run hiện có; không bắt lỗi render
  để đổi sang fallback hoặc công bố một file hỏng thành thành công.

Giao diện một nút và API cũ giữ nguyên. Chọn nhịp **Năng động theo mẫu mới**,
bật **Tự thêm ảnh và đồ họa minh họa theo lời nói**. Dựng lại để áp dụng vào
video cũ. Chế độ tinh gọn không tự chèn bộ ảnh mới. Tắt minh họa hoặc yêu cầu
không chèn ảnh sẽ tắt ảnh tự chọn; ảnh tải lên vẫn theo yêu cầu riêng hiện có.

## Giới hạn

Kho ảnh ban đầu chỉ có hai nhóm chủ đề, chưa bao phủ mọi ngành. Khi không
khớp, tool giữ camera hoặc đồ họa có căn cứ; cần tải ảnh đúng chủ đề hoặc
bổ sung kho ảnh được kiểm tra. Không ép dùng robot/nhóm họp vào video yoga,
sản phẩm, y tế hoặc nội dung khác không phù hợp. Không tự tìm stock Internet,
lấy ảnh đối thủ, tạo góc máy mới hoặc dựng footage sự kiện không có nguồn.
Bộ ảnh là tài nguyên dựng sẵn có provenance; không phải model tự sinh ảnh
cho mỗi lần bấm. Quy tắc/skill dựng không thay thế việc fine-tune trọng số.

Kiểm chứng thực tế và khác biệt còn lại:
[verification/REFERENCE_VISUALS_VERIFICATION.json](verification/REFERENCE_VISUALS_VERIFICATION.json).
