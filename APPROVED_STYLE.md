# Dựng theo mẫu đã duyệt

Phong cách được người dùng duyệt ngày 11/10/2026: video dọc 720×1280, giọng nói nguồn, người nói xen với thẻ trắng, pill teal/navy, tiêu đề Barlow Condensed, phụ đề Inter và SFX nhẹ. Đây là bộ dựng dùng chung, không gắn tên AN NA hoặc một timeline cố định vào mọi nguồn.

## Chạy trên máy Windows

Cài Python, FFmpeg/FFprobe, Node.js 22.12+ và Chrome. Trong thư mục repo:

```powershell
python -m pip install -r requirements.txt
npm --prefix motion_engine install
# CPU int8, ít bộ nhớ hơn Whisper/PyTorch; chỉ cần một bộ nhận dạng:
python -m pip install -r requirements-ai-fast.txt
ollama pull qwen3:4b
python main.py
```

Lần đầu model nhận dạng và model Ollama cần tải về; sau đó chạy tại máy. Không cần API AI trả phí hoặc train model. Nếu Chrome cài ở nơi khác, trước khi chạy:

```powershell
$env:CHROME_PATH='C:\Program Files\Google\Chrome\Application\chrome.exe'
```

Có thể tiếp tục dùng requirements-ai.txt / openai-whisper nếu đã cài. Khi cả hai bộ có mặt, tool ưu tiên faster-whisper. WHISPER_MODEL chọn model nhận dạng; mặc định small khi dùng faster-whisper. Model Ollama lấy từ VIDEO_AI_MODEL; chọn model đã tải phù hợp máy chạy final. Model nhỏ có thể cần sửa storyboard; engine kiểm tra và yêu cầu model sửa một lần, rồi báo lỗi rõ nếu chưa hợp lệ.

## Dùng tool

1. Tải video chính lên dự án.
2. Bấm **Dùng mẫu đã duyệt**. Nút điền prompt, chọn phong cách DANAVA, AI và giữ toàn bộ nội dung. Có thể sửa prompt.
3. Bật nhận dạng phụ đề, hoặc nhập SRT đã kiểm tra. Tên riêng có thể nhận dạng sai; sửa phụ đề trước khi dựng nếu cần.
4. Dòng thương hiệu là tùy chọn. Có thể tải ảnh/video thật hoặc nhạc nền.
5. Bấm **AI dựng thử 12 giây**, rồi **Xuất bản đã chỉnh** để giữ cùng storyboard cho bản đầy đủ. **AI dựng & xuất video** tạo một storyboard mới.

Prompt mẫu:

> Dựng theo mẫu DANAVA đã duyệt: video dọc 9:16, giữ toàn bộ lời nói và thời lượng. Xen kẽ người nói với thẻ trắng theo ý nghĩa; chữ lớn phía trên mặt, phụ đề ngắn; thẻ teal/navy. Chọn minh họa hội thoại, quy trình hoặc kết nối đúng nội dung. SFX pop/whoosh nhẹ ở điểm nhấn, không át giọng. Không lặp lịch hiệu ứng cố định, không bịa số liệu, không chèn thương hiệu khác. Kết thúc trên người nói nếu không có CTA thật.

## AI quyết định gì?

`ai_director.py` gửi prompt, transcript, timeline và tài nguyên cho Ollama. AI trả dữ liệu storyboard theo schema, không trả code hoặc lệnh shell. Scene bao gồm timeline_start, duration, scene_type, headline/badge, graphic_kind/title/items, visual_asset_id, animation_in/out, sound_effect/volume. Engine từ chối storyboard thiếu độ dài, chồng cảnh, tài nguyên không thuộc dự án, dữ liệu so sánh thiếu hoặc B-roll quá ngắn.

- `chat`: hình hội thoại minh họa; tối đa 3 dòng hội thoại từ nội dung.
- `process`: sơ đồ tối đa 3 ý/bước.
- `network`: sơ đồ kết nối, tối đa 5 nhánh.
- `visual_asset_id`: ảnh/video thật của dự án; B-roll dùng chuyển động từ video hoặc ảnh toàn khung. Thẻ minh họa dùng frame từ video nếu chọn tài nguyên video.
- `talking_head_pip`: bố cục trắng với người nói phía dưới.
- `comparison`, `statistic`, `step_list`, `cta`: nội dung phải lấy từ lời thoại, không dùng ví dụ kinh doanh viết sẵn.

Render dùng chung typography/đồ họa của mẫu đã duyệt. Phụ đề dài chia thành cụm ngắn theo timestamp từng từ của bộ nhận dạng; timestamp được ánh xạ sau khi cắt. Với SRT nhập sẵn không có timestamp từ, các cụm được chia theo tỷ lệ số từ trong segment. Người dùng có thể sửa SRT để khớp hơn. Cảnh camera hiện chữ phía trên, tránh vùng mặt của bố cục nguồn trong mẫu. Tool chưa tự theo dõi khuôn mặt, nên cần xem lại video có góc quay khác.

## Giới hạn được ghi rõ

Bộ dựng không tự tìm stock trên Internet hoặc tạo ảnh photorealistic. Đồ họa tạo tại máy là minh họa khái niệm, không phải screenshot thật hay số liệu chứng thực. Nhạc chỉ được thêm khi tải file lên; SFX tổng hợp tại máy. Chưa kiểm chứng model Ollama thật trong môi trường phát triển; kiểm thử AI dùng phản hồi có kiểm soát để kiểm tra hợp đồng, repair và API. Chất lượng chọn cảnh còn phụ thuộc model và transcript.

Hai chế độ AI và quy tắc vẫn riêng biệt. Chế độ quy tắc không đọc prompt bằng model và không được báo như AI.
