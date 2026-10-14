# Duyệt câu và chuẩn bị dữ liệu phong cách

Đây là quy trình thu thập phản hồi có xác nhận; không phải fine-tune model.
Giữ nguyên luồng một nút tạo video, API dựng, schema storyboard và dữ liệu cũ.

## Cách sử dụng

1. Tạo video và mở **Sửa phụ đề trước khi dựng lại**.
2. Với câu có cảnh báo, bấm **Nghe câu gốc**. Sửa câu nếu sai, **Lưu phụ đề**
   rồi dựng lại để MP4 dùng đúng bản chữ vừa lưu.
3. Khi đã nghe và kiểm tra, bấm **Đã nghe và xác nhận câu này**. Không cần
   cố tình thay chữ của một câu vốn đúng để xóa cảnh báo. Nút không xác minh
   âm thanh tự động: đây là xác nhận của người dùng.
4. Xem MP4, kiểm tra tất cả phụ đề, bố cục và minh họa. Đánh dấu **Tôi đã
   kiểm tra phụ đề của bản này**, rồi **Duyệt phong cách**.
5. Xem số bản đã duyệt cả chữ/hình và số nguồn khác nhau. Xuất đúng tệp cần
   dùng: bản phong cách cũ vẫn chứa cả bản chưa duyệt chữ; bản **đã duyệt cả
   chữ và hình** chỉ chứa các xác nhận đủ bằng chứng mới.

Không tự coi bản nhận dạng, fallback hoặc phản hồi được nhập từ trước là dữ
liệu đã duyệt. Có thể duyệt riêng phong cách và quay lại duyệt chữ sau.
Không dùng một số lượng mẫu tùy ý để tuyên bố model đã đủ chất lượng train.

## Ràng buộc xác nhận

`POST /api/projects/{id}/subtitle-review` nhận revision, subtitle_index và
confirmed. Server từ chối revision cũ, index sai và tác vụ đang chạy. Dấu xác
nhận gắn SHA-256 của asset ID, hash nguồn, câu chữ và khoảng thời gian nguồn.
Đổi một thành phần làm xác nhận đó hết hiệu lực; xác nhận không chuyển sang
video khác. Client sửa `/edit_plan` không thể tự nhập dấu xác nhận hoặc lịch
sử cảnh báo. Lịch sử giữ lý do nhận dạng cần nghe để bỏ xác nhận vẫn khôi
phục cảnh báo ngay cả khi renderer đã dựng lại word alignment.

Xác nhận nghe lại không thay đổi pixel/âm thanh nên không tăng revision
nội dung hoặc yêu cầu render lại. Chỉnh chữ vẫn tăng revision và đòi dựng
lại như trước. Bỏ xác nhận thu hồi trạng thái đã kiểm tra phụ đề của đúng
bản dựng; không sao chép một đánh giá của bản cũ sang bản mới.

## Dữ liệu xuất

- `/api/learning/export`: hợp đồng cũ, phản hồi phong cách đã duyệt.
- `/api/learning/reviewed-export`: cùng định dạng style supervision, chỉ lấy
  bản approve_style có xác nhận toàn bộ chữ, nguồn có hash, phụ đề không
  rỗng, không còn cảnh báo chưa xác nhận và output đúng revision thành công.
- `/api/learning`: bổ sung reviewed_examples, reviewed_sources,
  style_only_examples và dataset_kind=style_supervision. Các trường cũ giữ nguyên.

Record mới thêm review_evidence; record cũ vẫn đọc và dùng làm tham khảo
phong cách, nhưng không tự được đưa vào tập reviewed. Không thêm transcript,
tên asset, đường dẫn video hoặc hash nguồn vào JSONL xuất. Ghi chú tự do vẫn
được xuất nguyên như người dùng đã nhập; cần xem lại ghi chú trước khi chia sẻ.
JSONL này không chứa cặp transcript → storyboard, không phải bộ dữ liệu SFT
có thể đưa thẳng vào trainer. Chưa có thao tác thay trọng số/model tự học.

## Kiểm chứng

Xem [verification/REVIEW_DATASET_VERIFICATION.json](verification/REVIEW_DATASET_VERIFICATION.json)
cho kiểm thử API, trình duyệt, video thứ hai và các giới hạn thực tế.
Chạy trong virtual environment hiện có: `python main.py`, tải lại trang để
nhận JavaScript mới. Không cần thêm dependency production hoặc API trả phí.
