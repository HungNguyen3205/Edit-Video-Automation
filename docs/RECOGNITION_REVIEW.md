# Nhận dạng tên, cache và kiểm chứng model thật

## Thay đổi

`backend/recognition_config.py` tạo gợi ý chỉ từ thương hiệu và tên chuẩn
của dự án hiện tại. Không đưa alias sai vào initial_prompt; không lấy tên từ
video cũ. Gợi ý tối đa 300 ký tự, không cắt dở một tên. Cả faster-whisper và
Whisper nhận gợi ý này trước khi nhận dạng. Đây là ngữ cảnh, không bảo đảm
mọi từ được nhận dạng chính xác.

Upload ghi SHA-256 ngay khi đọc từng chunk, không đọc toàn bộ file vào RAM.
Cache nhận dạng mới gắn asset, hash nguồn, engine, model, ngôn ngữ, compute
type và hash gợi ý. Đổi tên chuẩn/model/nguồn làm cache hết hiệu lực; đổi
alias nhưng giữ tên chuẩn không bắt nhận dạng lại. Dữ liệu dự án cũ/SRT
chưa có cache key vẫn đọc được. Phụ đề đã sửa thủ công tiếp tục ưu tiên.
Cache key thuộc server, client sửa plan không thể tự thay khóa này.

Global recognizer đổi đúng model khi WHISPER_MODEL thay đổi trong process;
không tiếp tục dùng object của model trước. Không thêm dependency production.

## Duyệt phụ đề

Trong phần sửa phụ đề, điền thương hiệu và các dòng `Tên chuẩn | alias`,
bấm **Áp dụng tên riêng vào bản nháp**. Giao diện hiện các câu trước → sau.
Đây chỉ là bản nháp: nghe câu gốc, kiểm tra rồi bấm **Lưu phụ đề** để áp dụng
vào dự án. Reload không mất bản đã lưu. Không tự ghi đè câu đã sửa chỉ vì
nhập lại tên; không gửi thêm request AI để sửa tên.

`POST /api/projects/{id}/subtitle-name-draft` nhận revision, brand_name,
proper_names và subtitles. Endpoint chỉ trả bản nháp và các thay đổi; không
thay revision, file video hay dữ liệu dự án. Revision cũ bị từ chối 409.
Lưu bản nháp vẫn qua `/edit_plan` hiện có, với validation và revision guard.

## Kiểm chứng Ollama

Lần này đã cài được runtime Ollama CPU và Qwen3 4B Q4_K_M thật, không dùng
API trả phí. Model lấy từ registry chính thức; từng layer xác minh SHA-256.
Một lần thử planner lạnh đã tạo 6 cảnh, 2 minh họa, không repair trong
97,070 giây: tải 3,598 giây, prompt 21,507 giây, sinh 71,918 giây, 357 token
đầu ra, stop bình thường. Prompt 1.632 token, think=false, context=8192,
num_predict=3840. Đây là inference thật, không phải fine-tune trọng số.

Không dùng kết quả này để kết luận tốc độ trên mọi máy. Có tác vụ kiểm thử
khác chạy trong một số phép đo. Máy thử có 9 logical CPU hiển thị, quota
8 CPU, RAM 9,7 GiB, không GPU/swap. Model đang chạy được báo khoảng 3,89 GB,
size_vram=0. Deadline không tăng; vẫn 180 giây chung trong luồng một nút.

Kết quả đầu cuối và các test nằm trong
[verification/REAL_AI_VERIFICATION.json](verification/REAL_AI_VERIFICATION.json).

## Giới hạn

- Whisper vẫn có thể nhận sai từ tiếng Việt; cần nghe và duyệt trước khi đăng.
- Gợi ý tên không phải bằng chứng lời nói đã được kiểm chứng.
- Không tự coi transcript nhận dạng hoặc kế hoạch AI là dữ liệu đã được duyệt
  để fine-tune. Chỉ phản hồi người dùng duyệt được lưu theo cơ chế hiện có.
- Một video chạy AI thành công không chứng minh chất lượng tương đương editor
  chuyên nghiệp trên mọi nội dung; cần thử thêm các video thực tế đa dạng.

## Hai lỗi chất lượng phát hiện khi xem MP4

Tiêu đề có thể thành ba dòng dù PIL đã tính hai dòng, do width và letter
spacing thực của Chrome. Chế độ năng động bỏ letter spacing dư, đo chữ
sau khi font load, giảm cỡ nếu cần và từ chối tiêu đề vẫn vượt safe area
hai dòng. Test dùng đúng font tiếng Việt Be Vietnam Pro và FFmpeg decode.

Các label sơ đồ trước đây được kiểm tra bằng vocabulary toàn video. Vì
vậy model có thể mượn ý ở cảnh trước sang cảnh hiện tại. `scene_graphic_errors`
giới hạn process/network vào lời của cảnh hoặc thông tin brief cung cấp,
yêu cầu nhãn có từ gắn với ý. Chat giữ từ trung tính hội thoại. Khi repair,
label enum thu hẹp theo cảnh cần sửa và giữ các cảnh đã hợp lệ. Không thay
đổi schema/API đầu ra, không tăng timeout hay giả kế hoạch thành công.

Phép thử model thật sau khi siết grounding ban đầu còn lặp nhãn chung ở
cảnh sửa; 3 request kết thúc bình thường nhưng kế hoạch vẫn bị từ chối
sau 170 giây. Pipeline đã dùng fallback và giữ 5 cảnh AI hợp lệ, không
coi JSON hợp lệ là kế hoạch đúng nội dung. Bản sửa cuối lọc label enum của
repair theo từ gắn với cảnh; nếu cảnh không có đủ hai ý, schema chỉ cho
phép camera thay vì ép một sơ đồ. Không tăng deadline để che lỗi này.

Sau thay đổi enum, model thật sửa đúng một cảnh trong một request repair;
planning hoàn tất sau 111,489 giây với hai request và không dùng fallback.
ASR của cùng dự án được dùng lại (0 giây), không nhận dạng lại để thử planner.
Bộ kiểm thử cuối bao gồm cache, grounding, repair, fallback, cancellation,
xuất lại và kiểm tra layout trong Chrome thật; kết quả ghi trong JSON kiểm chứng.

## Chạy trên máy người dùng

Giữ model đã có `qwen3:4b` trong Ollama. Trong thư mục repo, PowerShell:

```powershell
$env:VIDEO_AI_MODEL='qwen3:4b'
$env:WHISPER_MODEL='small'
python main.py
```

Khởi động lại backend sau khi cập nhật code; tải lại trang để nhận JS mới.
Không cần API AI trả phí. Máy kiểm thử không phải bảo đảm thời gian chạy
trên máy khác. Bộ nhớ feedback tiếp tục là style memory, chưa fine-tune.

Adapter cũng bỏ nhãn trùng và nhãn hội thoại không có căn cứ ở cảnh/brief.
Nếu sơ đồ chỉ còn một nhãn, chỉ dùng thêm tiêu đề mà model đã chọn khi tiêu
đề đó là ý thứ hai hợp lệ. Không sinh câu mới để lấp ô. Các scene đã chuẩn
hóa được ghi trong `normalized_label_scene_indices`. Compiler áp dụng cùng
quy tắc trước khi vẽ asset để các plan AI cũ cũng được render nhất quán.
Bản MP4 cuối dùng lại kế hoạch Qwen3 đã thành công; bước làm sạch nhãn này
là adapter engine, không được coi là một lượt model suy luận mới.

Xuất lại qua `/export` trước đây mặc định dùng renderer tinh gọn dù project
đang lưu storyboard motion. Bản này dùng `render_profile` đã lưu khi caller
không chỉ định style; nếu caller chỉ định rõ thì vẫn ưu tiên caller. Vì vậy
xuất lại kế hoạch AI không bị mất minh họa và không cần gọi model lại.

Nhãn trong bong bóng chat chỉ lấy từ cảnh đang nói hoặc từ hội thoại trung
tính; không mượn các từ khác trong brief để ghép thành cụm cụt ý. Tiêu đề
nhận diện nhân vật vẫn được kiểm tra theo cảnh/brief như trước.

Kiểm tra cuối: 162 test pass (1 cảnh báo deprecation của dependency). Bản
xuất lại cuối mất 105,984 giây gồm render 103,614 giây và xác minh 1,022
giây. Các thời gian graphics/scene render nằm trong render, không cộng hai
lần. MP4 720×1280, AAC, đủ 37,3 giây; FFmpeg decode toàn bộ thành công.
Đối chiếu sóng âm 2–5 giây có độ trễ tốt nhất 0 ms, không thay cho duyệt
nghe của người dùng. Còn 4 cảnh báo cần duyệt phụ đề; chưa fine-tune.
