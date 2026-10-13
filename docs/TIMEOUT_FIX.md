# Sửa timeout AI — 12/10/2026

## Lỗi đã xác nhận trong code

Deadline 600 giây trước đây được kiểm tra bên trong vòng đọc dòng stream. Khi không có dòng mới, cancellation/deadline không được kiểm tra cho đến khi HTTP read timeout xảy ra. Deadline được khởi tạo lại cho từng request nên repair có thể tiếp tục thêm 600 giây mỗi lần. Frontend bắt chữ model trong thông báo timeout và báo nhầm thành thiếu thành phần.

Ảnh lỗi của người dùng xác nhận AI chạm giới hạn 10 phút, nhưng không đủ để kết luận nguyên nhân máy của họ sinh chậm: chưa có số đo CPU/RAM/GPU hoặc log Ollama của máy đó. Bản sửa không tuyên bố đã khắc phục sức mạnh phần cứng.

## Thay đổi, giữ nguyên kiến trúc

- Giữ API chat/director đồng bộ; bên trong dùng httpx.AsyncClient và một task I/O có deadline/cancellation kiểm tra mỗi 50ms, kể cả chưa nhận được chunk. Task bị hủy và được await cleanup trước khi trả worker. Không chạy request trong thread bỏ lại phía sau.
- Một ai_session bao quanh giai đoạn lập kế hoạch, dùng chung deadline cho các lần sửa và kiểm tra kế hoạch. Không tăng mặc định 600 giây; budget này không bao gồm nhận dạng hoặc render.
- Ngăn ghi kế hoạch/kết quả thành công sau khi người dùng hủy. Timeout không tự retry kết nối hoặc tạo thêm request render, không thay bản xuất cũ.
- Ghi log video_ai_request/video_ai_result: cấu hình thực tế, số ký tự đầu vào/đầu ra, thời gian chunk đầu, elapsed, trạng thái và metadata token/thời gian Ollama cung cấp. Không log toàn bộ transcript hoặc video. Metadata thành công/thất bại nằm thêm ở job.ai_diagnostics; bản thành công có director.diagnostics. Đây là trường bổ sung, không thay API/schema dự án cũ.
- Bỏ bản transcript gửi trùng: mọi lời nói vẫn nằm trong các cảnh đã đánh chỉ số. Repair chỉ giữ source context và phản hồi lỗi gần nhất, không tích lũy cả lịch sử. Không cắt bớt nội dung nguồn.
- caption_text của model trở thành tùy chọn: không sửa thì engine giữ lời nhận dạng và timestamp. Model không phải chép lại toàn bộ phụ đề. Chỉnh sửa rõ ràng vẫn được kiểm tra như trước; không giả word alignment.
- num_predict được giới hạn theo số cảnh: min 2048, 768 + 512*số cảnh, max 16384; đường legacy mặc định 8192. Khi Ollama báo done_reason=length, từ chối phản hồi bị cụt thay vì render/đánh dấu thành công.
- UI phân biệt timeout, kết nối/stream, token limit, thiếu công cụ và lỗi kế hoạch. Giữ nguyên giao diện một video + prompt + nút dựng.

## Cấu hình tùy chọn ở máy chủ

| Biến môi trường | Mặc định | Vai trò |
| --- | --- | --- |
| VIDEO_AI_PLANNING_TIMEOUT | 600 | Tổng giây của giai đoạn AI, gồm repair/validation |
| VIDEO_AI_REQUEST_TIMEOUT | 600 | Tổng giây một request, vẫn bị giới hạn bởi budget chung |
| VIDEO_AI_READ_TIMEOUT | 300 | Giây chờ dữ liệu mạng; connect timeout giữ 10 giây |
| VIDEO_AI_MAX_TOKENS | Theo số cảnh | Ghi đè giới hạn sinh nếu cần; không đặt quá thấp |
| VIDEO_AI_THINK | 0 | Cấu hình hiện có; log ghi đúng giá trị thực tế |

Đây không phải các input dành cho người dùng. Giữ mặc định trước; dùng log để xác định điểm chậm, không kéo dài timeout để che lỗi. Hủy HTTP ở phía client không phải bằng chứng đảm bảo mọi phiên bản Ollama giải phóng bộ nhớ model ngay; ứng dụng đã đóng request và ngừng chờ/ghi kết quả.

## Kiểm tra

63 tests passed. Các test mới dùng HTTP server thật trả stream đứng im/liên tục, deadline ngắn, cancellation, read timeout, deadline chung qua hai request, validation vượt budget, stream thiếu done, token limit, native metrics và giữ output cũ khi AI thất bại. Bộ test duration/caption/audio/render hiện có vẫn đạt.

Browser thật với fixture model: hiển thị đúng lỗi trong ảnh thay vì báo thiếu thành phần; không hiện download mới khi thất bại; dựng lại thành công, tải MP4, refresh giữ kết quả, mobile 390px không tràn ngang.

Qwen3-4B-Q4_K_M thật qua Ollama CPU, think=false, num_ctx=8192: một request thành công; 917 input token + 637 output token = 1554 token. Request 77.801 giây; load model 10.598 giây, prompt eval 11.195 giây, generation 55.935 giây, chunk đầu 21.866 giây. Đây là token Ollama báo, không phải tín dụng ChatGPT.

API upload -> transcript/timestamp cache từ faster-whisper small đã nhận dạng thật trên đúng demo.mp4 -> AI thật -> render -> decode toàn bộ thành công. Không biên tập storyboard hoặc mock kết quả chọn cảnh. Source/timeline/storyboard/MP4 đều 37.3 giây, 720x1280, có audio. Đã xem các khung 2.5/10/16/23/28/34 giây, đồ họa và chữ hiển thị. Không khẳng định QA thị giác từng frame.

Một lần trước từng đo AI khoảng 125 giây với cấu hình cũ; điều kiện tải máy không kiểm soát hoàn toàn nên không dùng đó làm benchmark đảm bảo phần trăm tăng tốc. Chưa đo lại trên máy Windows của người dùng. Phụ đề nhận dạng vẫn có lỗi từ trong demo; phần sửa này không coi các từ chưa chắc đúng là đã sửa chính xác.

## Chạy lại

Dừng server cũ, cập nhật main, python main.py rồi Ctrl+F5 trên trang tool. Không cần package mới. Nếu vẫn chậm, xem video_ai_request/video_ai_result để biết giá trị think/model và thời gian load/prompt/generation trước khi đổi cấu hình.
