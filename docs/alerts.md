# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `P2-warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `fast_successful_requests` (latency ≤ 2000ms, target 99.5%/28 ngày) — `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 2000ms` liên tục 5 phút
- Ảnh hưởng tới người dùng: câu trả lời đến chậm; mỗi request chậm hơn 2000ms tiêu hao error budget 0.5%
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Latency** trên dashboard: xác nhận P95/P99 tăng, khoảng thời gian bắt đầu tăng, và TTFT P95 có tăng theo không (TTFT ổn định + tổng latency tăng ⇒ nghi ngờ retrieval, không phải LLM).
  2. Lọc `data/logs.jsonl` với `event == "response_sent"` và `latency_ms > 2000` trong khoảng đó, lấy một `correlation_id`.
  3. Mở trace Langfuse có `metadata.correlation_id` đó, so sánh thời lượng span `retrieval` và `llm-generate` để biết bước nào chậm.
- Mitigation tạm thời: nếu span `retrieval` chậm → chuyển sang fallback context/tắt bước retrieval chậm, kiểm tra vector store; nếu `llm-generate` chậm sau khi đổi prompt → rollback label `production` về version trước (xem `docs/PROMPT_VERSIONING.md`); nếu đang chạy practice scenario → `python scripts/inject_incident.py --scenario rag_slow --disable`.
- Owner: `student-2A202602507`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `P1-critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `fast_successful_requests` và guardrail `error_rate_pct_max: 2`, `retrieval_success_rate_pct_min: 90`
- Điều kiện và thời gian duy trì: `count(request_failed)/count(request_received)*100 > 2%` HOẶC `retrieval_success_rate_pct < 90%` trong 3 phút
- Ảnh hưởng tới người dùng: request trả HTTP 500, người dùng không nhận được câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Errors**: xem error rate, breakdown theo `error_type` và tỷ lệ retrieval success.
  2. Lọc log `event == "request_failed"`, đọc `error_type`, `tool_name`, `tool_success=false` và lấy `correlation_id` mới nhất.
  3. Mở trace cùng `correlation_id`: span `retrieval` có `level=ERROR` và status message ⇒ lỗi ở retrieval; nếu span đó bình thường thì kiểm tra `llm-generate`.
- Mitigation tạm thời: khôi phục kết nối vector store/dependency, bật fallback không cần retrieval, hoặc tắt incident practice (`--scenario tool_fail --disable`); thông báo cho người dùng nếu lỗi kéo dài > 15 phút.
- Owner: `student-2A202602507`

## Alert 3

- Tên: `CostPerRequestSpike`
- Severity: `P2-warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5` — `response_sent.cost_usd`, `tokens_out`
- Điều kiện và thời gian duy trì: `mean(cost_usd) > 0.006 USD/request` (baseline ~0.0024, tức ≥ 2.5×) hoặc tổng chi phí 60 phút > 2.5 USD, kéo dài 10 phút
- Ảnh hưởng tới người dùng: người dùng không thấy ngay, nhưng chi phí vận hành tăng bất thường và có thể làm hết ngân sách trong ngày; thường đi kèm câu trả lời dài bất thường
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Cost** và **Tokens**: xác nhận `tokens_out` (hoặc `tokens_in`) tăng và thời điểm bắt đầu.
  2. Lọc log `response_sent` có `cost_usd`/`tokens_out` cao, lấy `correlation_id`; nhóm theo `feature` để xem feature nào bị ảnh hưởng.
  3. Mở trace tương ứng, xem `usage_details`/`cost_details` của span `llm-generate` và `prompt_version` — prompt mới có sinh câu trả lời dài hơn không.
- Mitigation tạm thời: rollback label `production` về prompt version trước đó, đặt giới hạn `max_tokens`/độ dài câu trả lời, tạm giảm tải hoặc rate-limit feature gây tốn kém; tắt practice scenario `cost_spike` nếu đang chạy.
- Owner: `student-2A202602507`
