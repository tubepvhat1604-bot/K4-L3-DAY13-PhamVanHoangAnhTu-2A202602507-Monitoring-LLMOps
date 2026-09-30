# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mọi đường dẫn evidence là đường dẫn tương đối từ thư mục `submission/`.

## 1. Thông tin học viên

- **Họ và tên:** Phạm Văn Hoàng Anh Tú
- **MSSV:** 2A202602507
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/tubepvhat1604-bot/K4-L3-DAY13-PhamVanHoangAnhTu-2A202602507-Monitoring-LLMOps <!-- KIỂM TRA lại URL -->
- **Commit SHA cuối:** <!-- ĐIỀN: git log -1 --format=%H -->
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (incident `rag_slow`, affected feature `monitoring`, seed 1312, ngưỡng 2000 ms)
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602507`

## 2. Evidence index

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | [evidence/01-pytest.png](evidence/01-pytest.png) |
| Log validator | [evidence/02-log-validator.png](evidence/02-log-validator.png) (baseline 30/100, xem mục 3) |
| Dashboard validator | [evidence/03-dashboard-validator.png](evidence/03-dashboard-validator.png) |
| Structured log | [evidence/04-structured-log.png](evidence/04-structured-log.png) |
| PII redaction | [evidence/05-pii-redaction.png](evidence/05-pii-redaction.png) |
| Trace list | [evidence/06-trace-list.png](evidence/06-trace-list.png) |
| Trace waterfall | [evidence/07-trace-waterfall.png](evidence/07-trace-waterfall.png) |
| Trace metadata | [evidence/08a-trace-metadata-root.png](evidence/08a-trace-metadata-root.png), [evidence/08b-trace-metadata-generation.png](evidence/08b-trace-metadata-generation.png) |
| Prompt versions | [evidence/09-prompt-versions.png](evidence/09-prompt-versions.png), trace v2: [evidence/09b-trace-v2.png](evidence/09b-trace-v2.png) |
| Prompt promote / rollback | [evidence/10a-prompt-promote.png](evidence/10a-prompt-promote.png), [evidence/10b-prompt-rollback.png](evidence/10b-prompt-rollback.png) |
| Dashboard runtime | [evidence/11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metric | [evidence/12-incident-metric.png](evidence/12-incident-metric.png) |
| Incident log | [evidence/13-incident-log1.png](evidence/13-incident-log1.png) (lọc request chậm), [evidence/13-incident-log2.png](evidence/13-incident-log2.png) (log chi tiết `req-a34983bf`) |
| Incident trace | [evidence/14-incident-trace.png](evidence/14-incident-trace.png), [evidence/14b-incident-trace-metadata.png](evidence/14b-incident-trace-metadata.png) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (thiếu field, 0 correlation ID, thiếu enrichment) | 100/100 | Chuyển `logs.jsonl` cũ ra ngoài repo trước khi đo lại vì validator đọc toàn bộ file |
| `validate_dashboard.py` | 6/6 | 6/6 | Contract hợp lệ từ đầu; phần việc thật là dashboard runtime (`scripts/build_dashboard.py`) |
| `pytest` | 22 passed | 36 passed | Thêm test PII, header/context, child observation, alert/SLO |
| Số traces hợp lệ | 0 | > 10 trong project cá nhân (xem `06`) | Mỗi request = root + 2 child observation |
| Số PII leak | chưa scrub | 0 | Gửi email + SĐT + CCCD + thẻ, log chỉ còn nhãn `[REDACTED_*]` |
| Latency P95 / TTFT P95 | ~155 ms / 50 ms | ~155 ms / 50 ms; lúc incident ~2652 ms / 50 ms | Fake LLM: 50 ms tới token đầu + 100 ms |
| Retrieval success rate | 100% | 100% | `rag_slow` làm chậm chứ không làm lỗi retrieval |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` (`app/middleware.py`) gọi `clear_contextvars()` đầu mỗi request, nhận `x-request-id` nếu khớp `^req-[0-9a-f]{8}$` (sai format thì bỏ qua để tránh log injection), không có thì sinh `req-<8 hex>`. ID được bind vào structlog, lưu ở `request.state`, trả lại qua header `x-request-id` + `x-response-time-ms` và đưa vào trace metadata.
- **Các metadata được ghi vào structured log:** `ts`, `level`, `service`, `event`, `correlation_id`, `user_id_hash` (SHA-256 cắt 12 ký tự, không log user_id thô), `session_id`, `feature`, `model`, `env`; `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` đứng **trước** `JsonlFileProcessor` và `JSONRenderer` trong `configure_logging()`, duyệt đệ quy mọi field chuỗi (không chỉ `payload` cấp 1). Pattern trong `app/pii.py`: email, thẻ thanh toán, CCCD, SĐT VN (+84/0, ngăn cách bằng dấu cách/chấm/gạch), hộ chiếu, địa chỉ.
- **Cách kiểm chứng kết quả:** `02-log-validator` 100/100; `05-pii-redaction` gửi `a@b.vn 0901234567 001099012345 4111 1111 1111 1111` và log chỉ còn `[REDACTED_EMAIL] [REDACTED_PHONE_VN] [REDACTED_CCCD] [REDACTED_CREDIT_CARD]`; test tự động trong `tests/test_pii.py`, `tests/test_logging_context.py`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** mọi ảnh Langfuse có tên project `day13-k4-l3b-2A202602507`; mỗi trace có `correlation_id` trùng với dòng log trong `data/logs.jsonl` do tôi chạy.
- **Cấu trúc root/retrieval/generation observations:** `lab-agent-run` (agent, trace name `day13-agent-request`) là cha của `retrieval` (type `retriever`, lỗi → `level=ERROR`) và `llm-generate` (type `generation`, có `model`, `usage_details`, `cost_details`, link prompt managed). Không gửi input/output thô lên trace; chỉ gửi metadata an toàn (`query_preview` đã scrub, `doc_count`, `ttft_ms`, prompt name/label/version).
- **Cách nối trace với log:** `correlation_id` có trong mọi dòng log của request và trong trace metadata (`propagate_attributes`). Ví dụ `04` và `07`/`08a` dùng cùng `correlation_id` `req-55556666` (trace ID `928dba45863645cf3d28dcdaa2cf346c`).
- **Prompt name:** `day13-chat` (text prompt, biến `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** v1 — labels `baseline`, `production`.
- **Version/label candidate:** v2 — label `candidate` (thêm dòng `Answer in at most 3 sentences.`).
- **Trace ID của mỗi version:**
  - v1 / `production`: `007d9a8758ba538e217ed821ff5d6414` (`req-a1b2c3d4`)
  - v2 / `candidate`: `51e9b65b75c2054b96d8ce946e42a9f1` (`req-c0ffee03`)
  - sau promote (`production` → v2): `eef9e60a4ed4d34567993027fd69a1b8` (`req-c0ffee05`, `prompt_version=2`)
- **Cách promote và rollback `production`:** code chỉ hỏi Langfuse theo `LANGFUSE_PROMPT_LABEL`, không sửa code khi đổi version. Promote = gán label `production` cho v2 trên UI (`10a`); rollback = gán lại `production` cho v1 (`10b`). App cache prompt 60 giây nên sau khi đổi label cần chờ ~1 phút mới thấy version mới trên trace.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `python scripts/build_dashboard.py` đọc `data/logs.jsonl` theo đúng `config/dashboard.yaml` (60 phút, refresh 30 s) và sinh `dashboard.html`: latency (P50/P95/P99 + TTFT P95), traffic, errors (error rate + retrieval success), cost, tokens, quality; mỗi panel có đơn vị, threshold line và trạng thái OK/VI PHẠM (`11`).
- **SLO và lý do chọn:** `fast_successful_requests`: 99.5% request trong 28 ngày thành công và có latency ≤ 2000 ms. Baseline P95 ≈ 155 ms nên còn dư >10 lần, nhưng vẫn bắt được retrieval chậm (~2.65 s) và trùng ngưỡng `latency_threshold_ms` của challenge. Panel latency vẫn giữ threshold 3000 ms vì `dashboard.yaml` là contract chấm điểm.
- **Cách tính error budget:** 100% − 99.5% = 0.5%. Với 10.000 request/28 ngày, tối đa 50 request được lỗi hoặc chậm hơn 2000 ms. Hết budget thì ngừng promote prompt/cấu hình mới. Riêng đợt challenge có 5/5 request `monitoring` vượt 2000 ms, tức đốt 10% budget của cả tháng chỉ trong ~13 giây.
- **Ba alert và runbook tương ứng:** (1) `HighLatencyP95`: P95 > 2000 ms trong 5m, P2; (2) `HighErrorRate`: error rate > 2% hoặc retrieval success < 90% trong 3m, P1; (3) `CostPerRequestSpike`: cost/request > 0.006 USD (≈ 2.5× baseline 0.0024) trong 10m, P2. Cả ba symptom-based, Slack `#k4-l3b-alerts`, owner `student-2A202602507`; cấu hình ở `config/alert_rules.yaml`, runbook ở `docs/alerts.md#alert-1..3`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 2026-09-30 04:12:45Z → 04:12:56Z (11:12:45 → 11:12:56 giờ VN).
- **Triệu chứng từ metrics:** panel Latency (`12`): P95 tăng từ ~155 ms (baseline) lên ~2652 ms, vượt SLO và ngưỡng challenge 2000 ms. TTFT P95 giữ nguyên 50 ms, error rate 0%, retrieval success 100%, token/cost không đổi. Kết luận ban đầu: không phải lỗi, không phải LLM chậm, mà là một bước trước LLM bị chậm. (P95 vẫn dưới đường 3000 ms của contract nên panel báo OK; chính vì vậy SLO/alert được đặt ở 2000 ms.)
- **Log line và correlation ID liên quan:** lọc `response_sent` có `latency_ms > 2000` (`13-incident-log1`) ra đúng 5 request, cả 5 đều `feature=monitoring`, `latency_ms` 2651–2652, `ttft_ms` 50. Request đại diện (`13-incident-log2`): `correlation_id=req-a34983bf`, `ts=2026-09-30T04:12:50.667Z`, `latency_ms=2651`. Dòng `req-7cd0ae14` (20950 ms) cũng lọt bộ lọc nhưng bị loại vì là feature `qa`, xảy ra lúc 04:00 trước khi bật incident.
- **Trace ID và span gây ảnh hưởng:** trace `b1672d5ea79e64a67ce7837126a924cc` (`14`, `14b`): `lab-agent-run` = 2.65 s, trong đó `retrieval` = 2.50 s và `llm-generate` = 151 ms (tag `monitoring`, session `k4-l3b-challenge-s02`, `prompt_version=1`, `prompt_source=langfuse`). Span gây ảnh hưởng là `retrieval`, chiếm ~94% thời gian request.
- **Root cause:** bước retrieval (vector store/RAG) phản hồi chậm ~2.5 s mỗi lần (incident `rag_slow`). Evidence phụ: 5 request gửi đồng thời (concurrency 5) nhưng hoàn thành lần lượt cách nhau đúng ~2.65 s (04:12:45, :48, :50, :53, :55). Retrieval chậm dùng lời gọi chặn (`time.sleep`) bên trong endpoint `async`, nên chặn event loop và các request phải xếp hàng. `latency_ms` trong log (~2.65 s) không tính thời gian xếp hàng, nên người dùng cuối thực tế chờ tới ~13 s.
- **Fix action:** tắt nguồn gây chậm (`python scripts/inject_incident.py --disable`, tương đương khôi phục vector store), chạy lại load test và xác nhận P95 về ~155 ms trên dashboard.
- **Preventive measure:** (1) alert `HighLatencyP95` (> 2000 ms trong 5m) kèm runbook "TTFT bình thường + latency cao ⇒ kiểm tra span retrieval"; (2) đặt timeout cho retrieval (ví dụ 800 ms) và fallback trả lời không cần context khi quá hạn; (3) chạy retrieval ngoài event loop (`run_in_threadpool` hoặc client async) để một request chậm không kéo cả hàng đợi; (4) đo thêm latency ở middleware/phía client để thấy cả thời gian xếp hàng.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Không gửi input/output thô của prompt và câu trả lời lên Langfuse, chỉ gửi model/usage/cost và metadata đã scrub. Prompt chứa câu hỏi người dùng nên có thể chứa PII; regex scrub chỉ là heuristic, nên cách an toàn nhất là không đưa nội dung lên hệ thống bên ngoài. Tôi vẫn debug được nhờ `correlation_id` nối về log nội bộ, cùng `prompt_version`, `doc_count`, `ttft_ms`. Ngoài ra, helper `start_observation()` trong `app/tracing.py` gom API Langfuse một chỗ, giúp agent test được bằng fake client.
- **Một lỗi/blocker đã gặp:** Mạng tới `cloud.langfuse.com` chập chờn. (a) Terminal báo `Failed to export spans batch due to timeout`, trace không lên (mất cả lô 10 trace của một lần load test). (b) Lấy prompt quá 2 s nên SDK trả fallback: trace `0926d42355732906162ad8d93c9e3a26` ghi `prompt_source=local-fallback`, `prompt_fetch_error=LangfuseFallback`. (c) Trace `req-7cd0ae14` mất 20.95 s dù `retrieval` và `llm-generate` gần như 0, tức thời gian nằm ở bước lấy prompt qua mạng, chưa có span riêng.
- **Cách tìm nguyên nhân và xử lý:** Đọc log uvicorn (dòng `Failed to export`) và so metadata `prompt_source` trên trace. Xử lý: tăng `LANGFUSE_TIMEOUT=30`, gửi lô nhỏ hơn (`LANGFUSE_FLUSH_AT=5`, `LANGFUSE_FLUSH_INTERVAL=1`), và cho timeout lấy prompt cấu hình qua `LANGFUSE_PROMPT_FETCH_TIMEOUT` (mặc định vẫn 2 s để giữ đúng public test). Cơ chế fallback đã hoạt động đúng thiết kế: app không lỗi, và trace ghi đúng sự thật là prompt không lấy từ Langfuse. Trước đó tôi cũng sửa thứ tự pattern PII (thẻ bắt đầu bằng `0` bị nhận nhầm là SĐT) và mở rộng scrub sang mọi field.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics trả lời "có vấn đề gì, từ lúc nào": P95 tăng trong khi TTFT/error không đổi. Logs trả lời "request nào": lọc `latency_ms > 2000` ra đúng 5 request `monitoring` và `correlation_id` cụ thể. Trace trả lời "bước nào": cùng `correlation_id` cho thấy `retrieval` chiếm 2.5/2.65 s. Đi ngược thứ tự (mở trace ngẫu nhiên) dễ chọn nhầm, như dòng `req-7cd0ae14` chậm vì lý do khác hoàn toàn.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt là cấu hình ảnh hưởng trực tiếp tới chất lượng, token và cost. Gắn `prompt_version` vào mọi trace cho phép quy regression về đúng version. Label `production` cho phép promote/rollback không cần deploy. SLO/error budget biến "chậm" thành con số ra quyết định: đợt `rag_slow` đốt 10% budget tháng trong vài giây, đủ lý do để chặn thay đổi mới cho tới khi ổn định.
- **Điều quan trọng nhất đã học:** Một con số trung bình hoặc một ngưỡng dashboard có thể báo OK trong khi người dùng chịu ảnh hưởng (P95 2.65 s < 3 s; `latency_ms` 2.65 s nhưng người dùng chờ tới ~13 s). Cần đo đúng chỗ và đặt SLO theo trải nghiệm thực.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Regex PII chỉ là heuristic (không bắt được địa chỉ viết tự do). Bước lấy prompt chưa có span riêng nên độ trễ mạng chỉ suy ra được từ khoảng trống trên timeline. `latency_ms` chưa tính thời gian xếp hàng trong event loop. Dashboard là HTML tĩnh sinh từ log, không phải hệ thống giám sát thời gian thực.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace (`req-a34983bf`).
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác; `config/challenge.json` không được commit.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
