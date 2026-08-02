-- CyberGuard QA record RAG governance warnings (additive only).
-- Persists per-answer prompt-injection flags so history can surface
-- which references were filtered (rag_warnings on /qa/ask and SSE done).

ALTER TABLE qa_records ADD COLUMN rag_warnings JSON NULL COMMENT 'RAG 注入防护警告（docId:flag 列表）' AFTER response_time;
