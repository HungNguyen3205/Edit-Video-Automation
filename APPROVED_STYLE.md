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

Có thể tiếp tục dùng requirements-ai.txt / openai-whisper nếu đã cài. Khi cả hai bộ có mặt, tool ưu tiên faster-whisper. WHISPER_MODEL chọn model nhận dạng; mặc định small khi dùng faster-whisper. Model Ollama lấy từ VIDEO_AI_MODEL; chọn model đã tải phù hợp máy chạy final. Model nhỏ có thể cần sửa storyboard; engine kiểm tra và yêu cầu model sửa tối đa hai lần trong luồng một nút, rồi báo lỗi rõ nếu chưa hợp lệ.

## Dùng tool

1. Thả một video vào trang chính.
2. Nhập yêu cầu hoặc để trống để dùng phong cách đã duyệt.
3. Bấm **Tạo video của tôi**. Tool nhận dạng, chọn cảnh và xuất toàn bộ video. Xem và tải MP4 tại ô kết quả.

Style, thời lượng, nhận dạng, render và hiệu ứng đều được chọn phía máy chủ. Người dùng không phải chọn preset, preview 12 giây hoặc xuất lần nữa. Muốn thay nguồn, bấm vùng chọn video. Muốn đổi yêu cầu, nhập prompt mới rồi bấm dựng lại. Tên dự án được lấy từ tên file; video cũ nằm trong **Video của tôi**.

Dừng tool cũ, cập nhật code, chạy lại `python main.py`, rồi tải lại trang `http://127.0.0.1:8000/` để dùng giao diện mới. Trang thủ công cũ vẫn ở `/frontend/advanced.html`, dành riêng cho người cần chỉnh SRT/timeline.

## AI quyết định gì?

`automatic_director.py` chia lời nói thành các đơn vị ngữ nghĩa/timestamp và gửi toàn bộ lời thoại cùng prompt cho Ollama. AI chọn chữ, khái niệm minh họa, SFX và zoom. Engine hoàn thiện bố cục từ những khái niệm AI đã cung cấp, ưu tiên đoạn có nhãn khớp lời nói, rồi quyết định thời gian, không để model tính thời lượng hoặc cắt mất nguồn. Trang nâng cao vẫn dùng `ai_director.py` cho kế hoạch đầy đủ. AI trả dữ liệu storyboard theo schema, không trả code hoặc lệnh shell. Scene bao gồm timeline_start, duration, scene_type, headline/badge, graphic_kind/title/items, visual_asset_id, animation_in/out, sound_effect/volume. Engine từ chối storyboard thiếu độ dài, chồng cảnh, tài nguyên không thuộc dự án, dữ liệu so sánh thiếu hoặc B-roll quá ngắn.

- `chat`: hình hội thoại minh họa; tối đa 3 dòng hội thoại từ nội dung.
- `process`: sơ đồ tối đa 3 ý/bước.
- `network`: sơ đồ kết nối, tối đa 5 nhánh.
- `visual_asset_id`: ảnh/video thật của dự án; B-roll dùng chuyển động từ video hoặc ảnh toàn khung. Thẻ minh họa dùng frame từ video nếu chọn tài nguyên video.
- `talking_head_pip`: bố cục trắng với người nói phía dưới.
- `comparison`, `statistic`, `step_list`, `cta`: nội dung phải lấy từ lời thoại, không dùng ví dụ kinh doanh viết sẵn.

Render dùng chung typography/đồ họa của mẫu đã duyệt. Phụ đề dài chia thành cụm ngắn theo timestamp từng từ của bộ nhận dạng; timestamp được ánh xạ sau khi cắt. Khi AI sửa chính tả, từ không thay đổi giữ timestamp nhận dạng; tên được tách/gộp dùng khoảng thời gian của cụm từ gốc, không phải căn chỉnh âm thanh mới. Nếu không có timestamp từ thực tế thì không tự khai báo word alignment. Với SRT nhập sẵn không có timestamp từ, các cụm được chia theo tỷ lệ số từ trong segment. Người dùng có thể sửa SRT để khớp hơn. Cảnh camera hiện chữ phía trên, tránh vùng mặt của bố cục nguồn trong mẫu. Tool chưa tự theo dõi khuôn mặt, nên cần xem lại video có góc quay khác.

## Giới hạn được ghi rõ

Bộ dựng không tự tìm stock trên Internet hoặc tạo ảnh photorealistic. Đồ họa tạo tại máy là minh họa khái niệm, không phải screenshot thật hay số liệu chứng thực. Nhạc chỉ được thêm khi tải file lên; SFX tổng hợp tại máy. Kiểm thử tự động dùng phản hồi kiểm soát để kiểm tra hợp đồng, repair và API. Kết quả chạy model thật và kiểm tra video nguồn được ghi riêng trong PROJECT_STATUS.md. Chất lượng chọn cảnh còn phụ thuộc model và transcript. Nếu AI sửa phụ đề quá khác lời nhận dạng, engine giữ phụ đề nguồn ở cảnh đó và ghi cảnh báo; đây không phải xác minh chính tả bằng âm thanh. Tên riêng trong prompt được dùng để sửa cách viết trong kế hoạch, không ép bộ nhận dạng lặp theo prompt. Luồng một nút mặc định tắt suy luận dài để giảm thời gian chờ trên CPU. Có thể thử VIDEO_AI_THINK=1; cách này cần nhiều thời gian hơn và không bảo đảm chọn cảnh tốt hơn. Schema khóa số cảnh/mã cảnh và có ít nhất hai nhãn minh họa; engine chỉ hiển thị khái niệm hợp lệ, không tạo storyboard thay thế khi model thiếu/lỗi.

Hai chế độ AI và quy tắc vẫn riêng biệt. Chế độ quy tắc không đọc prompt bằng model và không được báo như AI.


Bộ phong cách có thể chuyển cảnh camera thành PIP/thẻ để hiển thị khái niệm minh họa mà AI đã viết, khi prompt yêu cầu minh họa nhưng model chưa bật bố cục đó. Mở đầu/kết thúc được giữ khi có cảnh giữa; lựa chọn dựa trên độ khớp nhãn với lời thoại, không theo chu kỳ số giây. `director.layout_adjustments` ghi các vị trí được engine hoàn thiện. Bộ kiểm tra từ vựng ngăn các nhãn mới như “AI đầu tiên”, “tối ưu thuật toán” khi không có trong nguồn; đây không phải xác minh sự thật của transcript.
