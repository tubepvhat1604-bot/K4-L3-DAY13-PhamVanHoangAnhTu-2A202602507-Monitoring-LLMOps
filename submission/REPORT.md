# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Phạm Văn Hoàng Anh Tú
- **MSSV:** 2A202602507
- **Lớp:** K4-L3B
- **Repository URL:** <!-- ĐIỀN: URL repo GitHub cá nhân -->
- **Commit SHA cuối:** <!-- ĐIỀN: chạy `git log -1 --format=%H` sau commit cuối -->
- **Challenge ID:** <!-- ĐIỀN sau khi Lab Coach gửi config/challenge.json ở CP3 -->
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602507`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.txt` (baseline: `evidence/00-baseline-log-validator.txt`) |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.txt` |
| PII redaction | `evidence/05-pii-redaction.txt` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (20/21 record thiếu field, 0 correlation ID hợp lệ, thiếu enrichment) | 100/100 | Xóa `logs.jsonl` cũ trước khi đo lại, vì validator đọc toàn bộ file |
| `validate_dashboard.py` | 6/6 | 6/6 | Contract đã hợp lệ từ đầu; phần việc thật là dựng dashboard runtime (`scripts/build_dashboard.py`) |
| `pytest` | 22 passed | 36 passed | Thêm test PII, header/context, child observation, alert/SLO |
| Số traces hợp lệ | 0 | <!-- ĐIỀN: ≥10, đếm trong Langfuse --> | Cần chạy workload với key Langfuse cá nhân |
| Số PII leak | 0 trên workload mẫu (baseline chưa gửi PII thật ra file vì mẫu 1 chỉ chứa email; xem 05) | 0, kể cả với input có email + SĐT + CCCD + thẻ | Kiểm tra bằng `grep` trên `data/logs.jsonl` |
| Latency P95 / TTFT P95 | ~155 ms / 50 ms | ~156 ms / 50 ms | Workload mẫu, fake LLM (sleep 50ms + 100ms) |
| Retrieval success rate | 100% (không có incident) | 100%; 0% khi bật `tool_fail` | Đo bằng `tool_success` trong log |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` (`app/middleware.py`) gọi `clear_contextvars()` đầu mỗi request, nhận `x-request-id` nếu khớp regex `^req-[0-9a-f]{8}$` (header sai format bị bỏ qua để tránh log injection), nếu không thì sinh `req-<8 hex>`. ID được `bind_contextvars`, lưu vào `request.state`, trả về qua header `x-request-id` và `x-response-time-ms`, đồng thời đưa vào trace metadata (`correlation_id`).
- **Các metadata được ghi vào structured log:** `ts`, `level`, `service`, `event`, `correlation_id`, và (bind trong `/chat`) `user_id_hash` (SHA-256 cắt 12 ký tự, không log user_id thô), `session_id`, `feature`, `model`, `env`; cùng `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success` ở `response_sent`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` được đăng ký trong `configure_logging()` **trước** `JsonlFileProcessor` và `JSONRenderer`, nên cả file `data/logs.jsonl` lẫn stdout đều nhận dữ liệu đã che. Processor duyệt đệ quy mọi field chuỗi (kể cả `payload` lồng nhau, `error detail`, `event`), không chỉ `payload` cấp 1. Pattern trong `app/pii.py`: email, thẻ thanh toán, CCCD, SĐT Việt Nam (+84/0, nhiều kiểu ngăn cách), hộ chiếu, địa chỉ (đường/phố/ngõ).
- **Cách kiểm chứng kết quả:** `validate_logs.py` 100/100 (`evidence/02-log-validator.txt`); gửi request chứa email + SĐT + CCCD + thẻ và grep file log = 0 kết quả (`evidence/05-pii-redaction.txt`); test tự động trong `tests/test_pii.py` và `tests/test_logging_context.py`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
- **Cấu trúc root/retrieval/generation observations:** `lab-agent-run` (agent, root, trace name `day13-agent-request`) → `retrieval` (type `retriever`, lỗi được đánh dấu `level=ERROR`) và `llm-generate` (type `generation`, có `model`, `usage_details` input/output/total, `cost_details`, link `prompt` managed). Input/output chỉ là bản đã scrub. Đã kiểm chứng quan hệ cha-con bằng OpenTelemetry in-memory exporter trước khi đẩy lên Langfuse.
- **Cách nối trace với log:** `correlation_id` có trong mọi dòng log và trong trace metadata (`propagate_attributes(metadata=...)`); tìm trace trong Langfuse bằng metadata `correlation_id`.
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:**
- **Cách promote và rollback `production`:**

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `python scripts/build_dashboard.py` đọc `data/logs.jsonl`, tính đúng theo `config/dashboard.yaml` (time range 60 phút, refresh 30s) và sinh `dashboard.html` gồm 6 panel: latency (P50/P95/P99 + TTFT P95), traffic, errors (error rate + retrieval success), cost, tokens, quality; mỗi panel có đơn vị, threshold line và trạng thái OK/VI PHẠM. Ảnh runtime: <!-- ĐIỀN: evidence/11-dashboard-overview.png -->.
- **SLO và lý do chọn:** `fast_successful_requests`: 99.5% request trong 28 ngày phải thành công và có latency ≤ 2000 ms. Baseline P95 ≈ 155 ms nên 2000 ms còn dư địa >10 lần, nhưng vẫn bắt được sự cố retrieval chậm (~2.65 s). Tôi siết ngưỡng SLO xuống 2000 ms so với mốc 3000 ms của panel latency; panel vẫn giữ 3000 ms vì dashboard.yaml là contract chấm điểm.
- **Cách tính error budget:** 100% − 99.5% = 0.5%. Với 10.000 request/28 ngày, tối đa 50 request được lỗi hoặc chậm hơn 2000 ms. Khi cạn budget thì đóng băng việc promote prompt/cấu hình mới.
- **Ba alert và runbook tương ứng:** (1) `HighLatencyP95` — P95 > 2000 ms trong 5m, P2; (2) `HighErrorRate` — error rate > 2% hoặc retrieval success < 90% trong 3m, P1; (3) `CostPerRequestSpike` — cost/request > 0.006 USD (≈2.5× baseline 0.0024) trong 10m, P2. Cả ba là symptom-based, gửi Slack `#k4-l3b-alerts`, owner `student-2A202602507`; cấu hình ở `config/alert_rules.yaml`, runbook ở `docs/alerts.md#alert-1..3`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Đặt helper `start_observation()` trong `app/tracing.py` thay vì gọi trực tiếp client Langfuse trong `agent.py`. Lý do: test có sẵn dùng fake client chỉ có `get_prompt`/`update_current_span`; gom logic vào adapter giữ agent test được, và khi thiếu key Langfuse thì SDK tự vô hiệu hóa nên app vẫn chạy bình thường.
- **Một lỗi/blocker đã gặp:** Thứ tự pattern PII trong starter khiến thẻ 16 số bắt đầu bằng `0` (ví dụ `0123 4567 8901 2345`) bị pattern SĐT nhận trước và gắn nhãn sai. Ngoài ra `scrub_event` gốc chỉ che `payload` cấp 1 nên PII nằm ở field khác hoặc payload lồng nhau vẫn lọt.
- **Cách tìm nguyên nhân và xử lý:** Viết test `test_card_is_not_mislabeled_as_phone`, xếp lại thứ tự (email → thẻ → CCCD → SĐT → hộ chiếu → địa chỉ), thêm lookaround `(?<!\d)…(?!\d)`; đổi `scrub_event` sang duyệt đệ quy mọi field chuỗi.
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Các mục cần Langfuse Cloud/challenge riêng (trace list, waterfall, metadata, prompt v1/v2, rollback, dashboard screenshot, điều tra incident CP3) phải chạy trên máy/project cá nhân và điền vào phần 2, 5, 7. Regex PII chỉ là heuristic (không bắt được địa chỉ viết tự do). `rag_slow` dùng `time.sleep` trong endpoint async nên chặn event loop: request đồng thời bị chậm dây chuyền (quan sát thấy ~13 s với concurrency 5).

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
