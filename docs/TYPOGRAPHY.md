# 10 bộ chữ theo chủ đề

Trong giao diện, mở **Kiểu chữ theo chủ đề · 10 lựa chọn**. Chọn một bộ,
xem trước chữ Việt rồi bấm nút tạo video như trước. Mặc định **Tự chọn theo
nội dung**: Ollama trả một `font_style` cho toàn bộ video. Nếu AI không khả
dụng hoặc chọn `auto`, engine chọn bằng từ khóa từ yêu cầu/lời nói và ghi
`selected_by: rules`. Lựa chọn thủ công luôn ưu tiên. Thay đổi lựa chọn cần
dựng lại MP4; không dùng font của kế hoạch cũ thay cho yêu cầu mới.

| ID | Font gốc | Chủ đề | Mục đích |
| --- | --- | --- | --- |
| `clean` | Inter | Kiến thức, chuyên gia, giáo dục | Phụ đề thông tin; tiêu đề ngắn, gọn. |
| `business` | Be Vietnam Pro | Doanh nghiệp, thương hiệu, dịch vụ | Phụ đề tiếng Việt; tiêu đề giới thiệu và tên thương hiệu. |
| `energetic` | Montserrat | Thể thao, fitness, sự kiện | Phụ đề ngắn; tiêu đề hành động nổi bật, không viết cả câu in hoa. |
| `friendly` | Nunito Sans | Gia đình, cộng đồng, sức khỏe đời sống | Phụ đề thân thiện; tiêu đề chia sẻ và giao tiếp. |
| `tutorial` | Open Sans | Hướng dẫn, bài học, thao tác | Phụ đề nhiều thông tin; tiêu đề từng bước; nhãn thao tác. |
| `technology` | Noto Sans | Công nghệ, AI, phần mềm | Phụ đề kỹ thuật; tiêu đề giải thích; nhãn sơ đồ. |
| `story` | Lora | Kể chuyện, văn hóa, hồi tưởng | Tiêu đề kể chuyện có chân; phụ đề chậm, đủ khoảng thở. |
| `editorial` | Noto Serif | Phỏng vấn, lịch sử, văn hóa, nội dung cao cấp | Tiêu đề trang nhã; phụ đề có chân rõ ở cỡ lớn. |
| `documentary` | Source Sans 3 | Tư liệu, báo cáo, phân tích | Phụ đề thông tin dài; tiêu đề giải thích, nhãn dữ kiện. |
| `impact` | Barlow Condensed | Quảng cáo, reels, khuyến mãi | Tiêu đề thật ngắn; phụ đề chữ hẹp dùng cỡ lớn hơn. |

## Vai trò của từng lớp chữ

- **Phụ đề:** giữ nguyên lời nói và thời gian; màu sáng, nền tối; tối đa hai
  dòng. Cỡ 32–36 trên khung thiết kế 720×1280, weight 500–700 tùy font.
- **Tiêu đề:** trích ý ngắn, có phân cấp; engine đo chiều rộng bằng chính
  font được chọn, giảm cỡ và cân bằng tối đa hai dòng, giữ tên đã khai báo.
- **Nhãn:** nhận diện loại ý/cảnh; ngắn, không lặp nguyên phụ đề.
- **Thương hiệu:** tên ở chân khung; logo giữ nguyên asset và nền trong suốt.

Một video dùng một bộ chữ nhất quán. Không đổi font ngẫu nhiên mỗi câu.
Lora/Noto Serif hợp nhịp kể chuyện hơn; Barlow Condensed ưu tiên tiêu đề
ngắn và phụ đề cỡ lớn. Đồ họa SVG sinh từ module minh họa vẫn dùng font
trung tính hiện có; ảnh/screenshot tải lên không bị thay chữ.

## File và cách tích hợp

- `skills/typography.json`: 10 profile, mục đích, vai trò, cỡ/weight, phân trang.
- `backend/typography.py`: lựa chọn có giới hạn, danh mục UI và font renderer;
  không sửa lời nói, timeline hay tạo đường dẫn từ đầu ra AI.
- `GET /api/typography`: danh mục cùng URL font cho xem trước.
- `POST /api/projects/{id}/make-video`: trường tùy chọn `font_style`, mặc
  định `auto`; tên sai bị từ chối 422. API cũ vẫn dùng được.
- Plan lưu `typography` gồm `profile_id`, `requested`, `selected_by`, `family`.
  Các plan cũ chưa có trường này giữ Inter/Barlow như trước khi export.

Font được đóng gói để render offline; tổng 20 file khoảng 1,8 MB. FontTools
chỉ dùng khi xây asset/kiểm thử, không thêm dependency cho người dùng chạy
video. Không tải font hay model khi bấm tạo video.

## Giấy phép và bảo trì

Font gốc lấy từ Google Fonts; giữ bản SIL Open Font License từng họ trong
`motion_engine/fonts/licenses/`. Bản static được giữ ký tự Việt/Latin và đổi
family nội bộ thành `AV Studio 01`…`10` để tôn trọng Reserved Font Names.
Không xóa attribution/copyright của font gốc. `typography-manifest.json`
ghi nguồn, SHA-256 đầu vào và từng asset. Tên thương mại trong danh mục là
font gốc dùng làm nền, không phải font độc quyền của dự án.

Dựng lại asset khi cần: chuẩn bị các file gốc và OFL.txt theo từng thư mục
họ Google Fonts; `python scripts/build_typography_fonts.py <sources_dir>`.
Cần dependency dev; không chạy tiện ích này trong job người dùng.

## Kiểm chứng

Đủ dấu Việt viết hoa/thường; kiểm tra family/weight thực tế; schema AI,
ưu tiên người dùng, từ chối ID sai, giữ câu nguồn, export plan cũ. Đã render
10 MP4 mẫu riêng, đọc log `fontselect` để xác minh font được dùng, decode
toàn bộ và xem khung hình. Giao diện đã thử đủ 10 xem trước, chọn Lora,
render, tải MP4 và khôi phục lựa chọn sau reload.

Môi trường kiểm thử không có Ollama hoạt động. Nhánh AI chọn font được thử
bằng phản hồi có kiểm soát; chất lượng chọn font của Qwen thật vẫn cần thử
trên máy chạy model. Đây là cấu hình/style guidance, chưa fine-tune model.

Kết quả: 128 test toàn dự án đã qua; sau thay đổi nhỏ cuối, 33 test font
đã qua. Video thật 37,3 giây giữ phụ đề đã duyệt, H.264 720×1280 + AAC,
decode toàn bộ thành công. Lần dựng lại dùng cache nhận dạng 0 giây,
lập kế hoạch dự phòng 0,120 giây, render 179,217 giây, kiểm tra 1,584 giây.
Đây không phải benchmark so sánh tốc độ vì tải CPU giữa các lần khác nhau.
Chi tiết: [bằng chứng](verification/TYPOGRAPHY_VERIFICATION.json).
