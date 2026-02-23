DEFAULT 2026-02-13T16:37:48.380983Z 2026-02-13 16:37:48,379 - app.mcp.tools.sec_nuggets - INFO - [SEC_NUGGETS_TOOL] Search: query='what is the outlook for the wind and wind energy composites market for 2026', ticker=F, type=None, section=None, signal=None
DEFAULT 2026-02-13T16:37:48.380995Z 2026-02-13 16:37:48,379 - app.mcp.tools.sec_nuggets - INFO - [SEC_NUGGETS_TOOL] Using semantic vector search
DEFAULT 2026-02-13T16:37:49.245482Z 2026-02-13 16:37:49,244 - app.db.semantic_search - INFO - [SEMANTIC_SEARCH] sec_filing_nuggets vector search: 10 results in 0.86s
DEFAULT 2026-02-13T16:37:49.245697Z 2026-02-13 16:37:49,244 - app.mcp.tools.sec_nuggets - INFO - [SEC_NUGGETS_TOOL] Returning 10 nuggets
DEFAULT 2026-02-13T16:37:49.246229Z INFO: 169.254.169.126:21280 - "GET /_next/static/chunks/28cdf12d298a2f1c.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:37:49.250659Z 2026-02-13 16:37:49,249 - app.mcp.tools.earnings_quotes - INFO - [EARNINGS_QUOTES_TOOL] Search: query='what is the outlook for the wind and wind energy composites market for 2026', ticker=DE, type=None, role=None, section=None
DEFAULT 2026-02-13T16:37:49.250674Z 2026-02-13 16:37:49,249 - app.mcp.tools.earnings_quotes - INFO - [EARNINGS_QUOTES_TOOL] Using semantic vector search
DEFAULT 2026-02-13T16:37:50.007736Z 2026-02-13 16:37:50,006 - app.db.semantic_search - INFO - [SEMANTIC_SEARCH] earnings_quotes vector search: 0 results in 0.76s
DEFAULT 2026-02-13T16:37:50.012517Z 2026-02-13 16:37:50,011 - app.mcp.tools.sec_nuggets - INFO - [SEC_NUGGETS_TOOL] Search: query='what is the outlook for the wind and wind energy composites market for 2026', ticker=DE, type=None, section=None, signal=None
DEFAULT 2026-02-13T16:37:50.012530Z 2026-02-13 16:37:50,011 - app.mcp.tools.sec_nuggets - INFO - [SEC_NUGGETS_TOOL] Using semantic vector search
DEFAULT 2026-02-13T16:37:50.796596Z 2026-02-13 16:37:50,795 - app.db.semantic_search - INFO - [SEMANTIC_SEARCH] sec_filing_nuggets vector search: 3 results in 0.78s
DEFAULT 2026-02-13T16:37:50.796608Z 2026-02-13 16:37:50,795 - app.mcp.tools.sec_nuggets - INFO - [SEC_NUGGETS_TOOL] Returning 3 nuggets
DEFAULT 2026-02-13T16:37:50.803358Z 2026-02-13 16:37:50,802 - app.agents.research.financial - INFO - Financial agent: Skipping company news (not needed for query type)
DEFAULT 2026-02-13T16:37:50.803372Z 2026-02-13 16:37:50,802 - app.agents.research.financial - INFO - Financial agent: Skipping press releases (not needed for query type)
DEFAULT 2026-02-13T16:37:50.803375Z 2026-02-13 16:37:50,802 - app.agents.research.financial - INFO - Financial agent: Skipping analyst ratings (not explicitly requested)
DEFAULT 2026-02-13T16:37:50.803379Z 2026-02-13 16:37:50,802 - app.agents.research.financial - INFO - Financial agent: Skipping sentiment analysis (not explicitly requested)
DEFAULT 2026-02-13T16:37:50.805508Z 2026-02-13 16:37:50,804 - app.utils.resilient_llm - INFO - Async invoking primary model: claude-sonnet-4-6 (message count: 2)
INFO 2026-02-13T16:37:50.915204Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 2.05 KiB] [httpRequest.latency: 8.727 s] [httpRequest.userAgent: Chrome 144.0.0.0] https://compositesdemo.ketzerointelligence.ai/api/evals/ingestion-health?days=30
INFO 2026-02-13T16:37:50.915500Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 124 B] [httpRequest.latency: 8.716 s] [httpRequest.userAgent: Chrome 144.0.0.0] https://compositesdemo.ketzerointelligence.ai/api/evals/reports?days=30&limit=20
INFO 2026-02-13T16:37:50.916152Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 1.32 KiB] [httpRequest.latency: 8.726 s] [httpRequest.userAgent: Chrome 144.0.0.0] https://compositesdemo.ketzerointelligence.ai/api/evals/dashboard?days=30
DEFAULT 2026-02-13T16:37:51.863826Z 2026-02-13 16:37:51,862 - app.api.routes.evals - WARNING - [EVALS] Articles trend query failed: 400 Unrecognized name: created_at at [6:19]; reason: invalidQuery, location: query, message: Unrecognized name: created_at at [6:19]
DEFAULT 2026-02-13T16:37:51.863841Z Location: us-central1
DEFAULT 2026-02-13T16:37:51.863846Z Job ID: d25366e9-1c71-446d-a782-a1b2920f3d45
DEFAULT 2026-02-13T16:37:52.454962Z INFO: 169.254.169.126:56580 - "GET /api/evals/ingestion-health?days=30 HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:37:52.636856Z 2026-02-13 16:37:52,635 - app.evals.token_tracker - INFO - [TOKEN_TRACKER] Flushed 2 records to BigQuery
DEFAULT 2026-02-13T16:37:52.636873Z 2026-02-13 16:37:52,635 - app.evals.quality_metrics - INFO - [EVAL_METRICS] Computing quality report for last 30 days
DEFAULT 2026-02-13T16:37:53.714693Z 2026-02-13 16:37:53,713 - app.evals.quality_metrics - INFO - [EVAL_METRICS] Quality report complete: 33 research reports, 4 briefings
DEFAULT 2026-02-13T16:37:59.623030Z 2026-02-13 16:37:59,621 - app.evals.anomaly_detection - INFO - [ANOMALY] Detected 1 anomalies
DEFAULT 2026-02-13T16:37:59.627457Z INFO: 169.254.169.126:56584 - "GET /api/evals/reports?days=30&limit=20 HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:37:59.629836Z INFO: 169.254.169.126:56588 - "GET /api/evals/dashboard?days=30 HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:38:16.971040Z 2026-02-13 16:38:16,969 - app.utils.resilient_llm - INFO - Primary model (claude-haiku-4-5) succeeded in 29.43s
DEFAULT 2026-02-13T16:38:16.971223Z 2026-02-13 16:38:16,969 - app.agents.research.visual - INFO - LLM selected 8 visuals from 29 candidates
DEFAULT 2026-02-13T16:38:16.971233Z 2026-02-13 16:38:16,969 - app.agents.research.visual - INFO - Visual research complete: 8 visuals selected in 31.2s
DEFAULT 2026-02-13T16:38:17.587972Z 2026-02-13 16:38:17,586 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 99s elapsed, loop iterations: 2147, active nodes: {'financial_research', 'industry_research'}, completed: {'groom', 'visual_research'}
DEFAULT 2026-02-13T16:38:43.310230Z 2026-02-13 16:38:43,307 - app.utils.resilient_llm - INFO - Primary model (claude-sonnet-4-6) succeeded in 52.50s
DEFAULT 2026-02-13T16:38:43.310527Z 2026-02-13 16:38:43,308 - app.agents.research.financial - INFO - [FINANCIAL_RESEARCH] COMPLETE in 116.5s - findings: 10
DEFAULT 2026-02-13T16:38:47.650729Z 2026-02-13 16:38:47,649 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 129s elapsed, loop iterations: 3096, active nodes: {'industry_research'}, completed: {'groom', 'financial_research', 'visual_research'}
DEFAULT 2026-02-13T16:38:58.545511Z INFO: 169.254.169.126:62325 - "GET /health HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:39:17.704293Z 2026-02-13 16:39:17,702 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 159s elapsed, loop iterations: 3607, active nodes: {'industry_research'}, completed: {'groom', 'financial_research', 'visual_research'}
DEFAULT 2026-02-13T16:39:47.708360Z 2026-02-13 16:39:47,706 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 189s elapsed, loop iterations: 4115, active nodes: {'industry_research'}, completed: {'groom', 'financial_research', 'visual_research'}
DEFAULT 2026-02-13T16:39:54.092213Z 2026-02-13 16:39:54,090 - app.utils.resilient_llm - INFO - Primary model (claude-sonnet-4-6) succeeded in 126.56s
DEFAULT 2026-02-13T16:39:54.092223Z 2026-02-13 16:39:54,091 - app.agents.research.industry - INFO - [INDUSTRY_RESEARCH] COMPLETE in 157.4s - findings: 25
DEFAULT 2026-02-13T16:39:54.098762Z 2026-02-13 16:39:54,097 - app.agents.research.synthesizer - INFO - [SYNTHESIZER] START - query: what is the outlook for the wind and wind energy c...
DEFAULT 2026-02-13T16:39:54.135287Z 2026-02-13 16:39:54,133 - app.utils.resilient_llm - INFO - Initialized resilient LLM: claude-opus-4-6 (Anthropic) -> gemini-2.5-pro (Gemini, max_tokens=20000)
DEFAULT 2026-02-13T16:39:54.135300Z 2026-02-13 16:39:54,133 - app.agents.research.synthesizer - INFO - [SYNTHESIZER] LLM initialized with max_tokens=20000 (non-thinking path)
DEFAULT 2026-02-13T16:39:54.135578Z 2026-02-13 16:39:54,134 - app.agents.research.synthesizer - INFO - [SYNTHESIZER] Quotable material: 7 quotes (2 exec, 2 SEC, 3 podcast)
DEFAULT 2026-02-13T16:39:54.136123Z 2026-02-13 16:39:54,134 - app.agents.research.synthesizer - INFO - [SYNTHESIZER] Prompt size: ~8,192 tokens (~32,768 chars) [system=1531, data=5889, planning=251, quotes=520]
DEFAULT 2026-02-13T16:39:54.136133Z 2026-02-13 16:39:54,135 - app.agents.research.synthesizer - INFO - [SYNTHESIZER] Calling Opus with timeout=360s, max_tokens=20000
DEFAULT 2026-02-13T16:39:54.136348Z 2026-02-13 16:39:54,135 - app.utils.resilient_llm - INFO - Async invoking primary model: claude-opus-4-6 (message count: 2)
DEFAULT 2026-02-13T16:40:17.722608Z 2026-02-13 16:40:17,721 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 219s elapsed, loop iterations: 4621, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
DEFAULT 2026-02-13T16:40:47.777539Z 2026-02-13 16:40:47,776 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 249s elapsed, loop iterations: 5158, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
INFO 2026-02-13T16:41:14.311438Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 9.67 KiB] [httpRequest.latency: 6 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/
DEFAULT 2026-02-13T16:41:14.318069Z INFO: 169.254.169.126:39108 - "GET / HTTP/1.1" 200 OK
INFO 2026-02-13T16:41:15.088758Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 47.58 KiB] [httpRequest.latency: 10 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/media/83afe278b6a6bb3c-s.p.3a6ba036.woff2
INFO 2026-02-13T16:41:15.089546Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 98.07 KiB] [httpRequest.latency: 16 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/6bde6e42b3cb4e8b.css
DEFAULT 2026-02-13T16:41:15.095397Z INFO: 169.254.169.126:39132 - "GET /_next/static/chunks/6bde6e42b3cb4e8b.css HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.096114Z INFO: 169.254.169.126:39120 - "GET /_next/static/media/83afe278b6a6bb3c-s.p.3a6ba036.woff2 HTTP/1.1" 200 OK
INFO 2026-02-13T16:41:15.851847Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 292.07 KiB] [httpRequest.latency: 53 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/4c3f70db625eef74.js
INFO 2026-02-13T16:41:15.852975Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 120.02 KiB] [httpRequest.latency: 48 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/b04e114bf66eaaf0.js
INFO 2026-02-13T16:41:15.853047Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 9.89 KiB] [httpRequest.latency: 39 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/turbopack-eea9f0fa150767f7.js
INFO 2026-02-13T16:41:15.853242Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 85.21 KiB] [httpRequest.latency: 47 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/0d7306d8285cf261.js
INFO 2026-02-13T16:41:15.853429Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 19.95 KiB] [httpRequest.latency: 41 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/0ac2c33f74cfed15.js
INFO 2026-02-13T16:41:15.853604Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 30.2 KiB] [httpRequest.latency: 42 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/185c188f8d239eac.js
INFO 2026-02-13T16:41:15.855594Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 1.74 KiB] [httpRequest.latency: 40 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/99e12d68b04a0060.js
INFO 2026-02-13T16:41:15.855916Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 535 B] [httpRequest.latency: 36 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/ff1a16fafef87110.js
INFO 2026-02-13T16:41:15.855933Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 27.45 KiB] [httpRequest.latency: 40 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/64c0a5e3a0354479.js
INFO 2026-02-13T16:41:15.856756Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 25.66 KiB] [httpRequest.latency: 38 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/935c116a1b1a81c3.js
INFO 2026-02-13T16:41:15.866721Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 17.52 KiB] [httpRequest.latency: 31 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/e4a57963ef362b98.js
DEFAULT 2026-02-13T16:41:15.870112Z INFO: 169.254.169.126:39148 - "GET /_next/static/chunks/4c3f70db625eef74.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.870172Z INFO: 169.254.169.126:39166 - "GET /_next/static/chunks/turbopack-eea9f0fa150767f7.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.878066Z INFO: 169.254.169.126:39198 - "GET /_next/static/chunks/0ac2c33f74cfed15.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.878857Z INFO: 169.254.169.126:39184 - "GET /_next/static/chunks/0d7306d8285cf261.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.878873Z INFO: 169.254.169.126:39174 - "GET /_next/static/chunks/185c188f8d239eac.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.879129Z INFO: 169.254.169.126:39202 - "GET /_next/static/chunks/99e12d68b04a0060.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.879496Z INFO: 169.254.169.126:39158 - "GET /_next/static/chunks/b04e114bf66eaaf0.js HTTP/1.1" 200 OK
INFO 2026-02-13T16:41:15.880862Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 40.29 KiB] [httpRequest.latency: 19 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/4747c033b699cef5.js
DEFAULT 2026-02-13T16:41:15.881465Z INFO: 169.254.169.126:39214 - "GET /_next/static/chunks/ff1a16fafef87110.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.881767Z INFO: 169.254.169.126:39204 - "GET /_next/static/chunks/64c0a5e3a0354479.js HTTP/1.1" 200 OK
INFO 2026-02-13T16:41:15.882604Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 98.61 KiB] [httpRequest.latency: 22 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/2dce929ef0456a8b.js
INFO 2026-02-13T16:41:15.882711Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 1.74 KiB] [httpRequest.latency: 26 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/6048b7400ad4bd52.js
DEFAULT 2026-02-13T16:41:15.883159Z INFO: 169.254.169.126:39222 - "GET /_next/static/chunks/935c116a1b1a81c3.js HTTP/1.1" 200 OK
INFO 2026-02-13T16:41:15.883416Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 111.52 KiB] [httpRequest.latency: 31 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/_next/static/chunks/fb791202ff9ac4a9.js
DEFAULT 2026-02-13T16:41:15.885262Z INFO: 169.254.169.126:39236 - "GET /_next/static/chunks/e4a57963ef362b98.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.898525Z INFO: 169.254.169.126:39252 - "GET /_next/static/chunks/4747c033b699cef5.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.899103Z INFO: 169.254.169.126:39266 - "GET /_next/static/chunks/6048b7400ad4bd52.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.901634Z INFO: 169.254.169.126:39268 - "GET /_next/static/chunks/2dce929ef0456a8b.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:15.903579Z INFO: 169.254.169.126:39298 - "GET /_next/static/chunks/fb791202ff9ac4a9.js HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:17.777684Z 2026-02-13 16:41:17,776 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 279s elapsed, loop iterations: 5697, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
INFO 2026-02-13T16:41:18.369402Z [httpRequest.requestMethod: GET] [httpRequest.status: 200] [httpRequest.responseSize: 96.17 KiB] [httpRequest.latency: 14 ms] [httpRequest.userAgent: Chrome 142.0.7444.162] https://compositesdemo.ketzerointelligence.ai/favicon.png
DEFAULT 2026-02-13T16:41:18.374978Z INFO: 169.254.169.126:39312 - "GET /favicon.png HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:41:47.777815Z 2026-02-13 16:41:47,776 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 309s elapsed, loop iterations: 6231, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
DEFAULT 2026-02-13T16:42:17.780346Z 2026-02-13 16:42:17,778 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 339s elapsed, loop iterations: 6769, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
DEFAULT 2026-02-13T16:42:47.845013Z 2026-02-13 16:42:47,843 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 369s elapsed, loop iterations: 7309, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
DEFAULT 2026-02-13T16:42:54.195798Z time="13/02/2026 04:42:54.193856" severity=INFO message="Starting a garbage collection run." mount-id=gen-lang-client-0436975498-c1-hub-data-d9793381
DEFAULT 2026-02-13T16:42:54.244410Z time="13/02/2026 04:42:54.242529" severity=INFO message="Garbage collection succeeded after deleted 0 objects in 48.543148ms." mount-id=gen-lang-client-0436975498-c1-hub-data-d9793381
DEFAULT 2026-02-13T16:43:17.855538Z 2026-02-13 16:43:17,853 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 399s elapsed, loop iterations: 7835, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
DEFAULT 2026-02-13T16:43:47.860144Z 2026-02-13 16:43:47,858 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 429s elapsed, loop iterations: 8377, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
DEFAULT 2026-02-13T16:43:58.549325Z INFO: 169.254.169.126:21037 - "GET /health HTTP/1.1" 200 OK
DEFAULT 2026-02-13T16:44:17.877573Z 2026-02-13 16:44:17,875 - app.api.routes.deep_research - INFO - [DEEP_RESEARCH] Heartbeat: 459s elapsed, loop iterations: 8912, active nodes: {'synthesize'}, completed: {'groom', 'financial_research', 'industry_research', 'visual_research'}
DEFAULT 2026-02-13T16:44:38.786087Z 2026-02-13 16:44:38,784 - app.utils.resilient_llm - INFO - Primary model (claude-opus-4-6) succeeded in 284.65s
DEFAULT 2026-02-13T16:44:38.789576Z 2026-02-13 16:44:38,787 - app.agents.research.synthesizer - INFO - [SYNTHESIZER] Hydrated visual blocks using 8 available visuals
DEFAULT 2026-02-13T16:44:38.789675Z 2026-02-13 16:44:38,788 - app.agents.research.synthesizer - INFO - [SYNTHESIZER] Normalized output: 8 sections, 8 key points
DEFAULT 2026-02-13T16:44:38.790571Z 2026-02-13 16:44:38,788 - app.agents.research.synthesizer - ERROR - [SYNTHESIZER] Failed to parse LLM output: 8 validation errors for SynthesisAgentOutput
DEFAULT 2026-02-13T16:44:38.790576Z sections.0.supporting_visuals.0
DEFAULT 2026-02-13T16:44:38.790580Z Input should be a valid dictionary or instance of SupportingVisual [type=model_type, input_value='0f365ebf-1d3d-4fcb-b22c-22bccd58b4d9', input_type=str]
DEFAULT 2026-02-13T16:44:38.790584Z For further information visit https://errors.pydantic.dev/2.10/v/model_type
DEFAULT 2026-02-13T16:44:38.790587Z sections.1.supporting_visuals.0
DEFAULT 2026-02-13T16:44:38.790591Z Input should be a valid dictionary or instance of SupportingVisual [type=model_type, input_value='cb0eff68-14a5-49fb-ab09-cdedeb1e218a', input_type=str]
DEFAULT 2026-02-13T16:44:38.790595Z For further information visit https://errors.pydantic.dev/2.10/v/model_type
DEFAULT 2026-02-13T16:44:38.790598Z sections.1.supporting_visuals.1
DEFAULT 2026-02-13T16:44:38.790602Z Input should be a valid dictionary or instance of SupportingVisual [type=model_type, input_value='245dc98c-7094-4ee3-a40a-8a20b973289a', input_type=str]
DEFAULT 2026-02-13T16:44:38.790606Z For further information visit https://errors.pydantic.dev/2.10/v/model_type
DEFAULT 2026-02-13T16:44:38.790609Z sections.3.supporting_visuals.0
DEFAULT 2026-02-13T16:44:38.790612Z Input should be a valid dictionary or instance of SupportingVisual [type=model_type, input_value='8424bfd6-04a8-4c28-9519-084a42396edf', input_type=str]
DEFAULT 2026-02-13T16:44:38.790616Z For further information visit https://errors.pydantic.dev/2.10/v/model_type
DEFAULT 2026-02-13T16:44:38.790620Z sections.3.supporting_visuals.1
DEFAULT 2026-02-13T16:44:38.790623Z Input should be a valid dictionary or instance of SupportingVisual [type=model_type, input_value='7a08ba8b-487a-46bd-813a-c4d3c4d3b4af', input_type=str]
DEFAULT 2026-02-13T16:44:38.790626Z For further information visit https://errors.pydantic.dev/2.10/v/model_type
DEFAULT 2026-02-13T16:44:38.790629Z sections.4.supporting_visuals.0
DEFAULT 2026-02-13T16:44:38.790633Z Input should be a valid dictionary or instance of SupportingVisual [type=model_type, input_value='24207525-f463-475f-876b-e7bd7859ef53', input_type=str]
DEFAULT 2026-02-13T16:44:38.790636Z For further information visit https://errors.pydantic.dev/2.10/v/model_type
DEFAULT 2026-02-13T16:44:38.790639Z sections.4.supporting_visuals.1
DEFAULT 2026-02-13T16:44:38.790646Z Input should be a valid dictionary or instance of SupportingVisual [type=model_type, input_value='160a91d8-272c-4b30-a9ec-7a1f7ac83e67', input_type=str]
DEFAULT 2026-02-13T16:44:38.790649Z For further information visit https://errors.pydantic.dev/2.10/v/model_type
DEFAULT 2026-02-13T16:44:38.790652Z sections.7.supporting_visuals.0
DEFAULT 2026-02-13T16:44:38.790656Z Input should be a valid dictionary or instance of SupportingVisual [type=model_type, input_value='f1d8643c-7a2d-4ca3-b44f-1a6c609530cb', input_type=str]
DEFAULT 2026-02-13T16:44:38.790659Z For further information visit https://errors.pydantic.dev/2.10/v/model_type
DEFAULT 2026-02-13T16:44:38.790662Z 2026-02-13 16:44:38,789 - app.agents.research.synthesizer - ERROR - [SYNTHESIZER] Raw LLM response (first 2000 chars): {
DEFAULT 2026-02-13T16:44:38.790665Z "report_id": "REP-1771000794",
DEFAULT 2026-02-13T16:44:38.790669Z "generated_at": "2026-02-13T16:39:54.134990",
DEFAULT 2026-02-13T16:44:38.790672Z "query": "what is the outlook for the wind and wind energy composites market for 2026",
DEFAULT 2026-02-13T16:44:38.790675Z "data_completeness": "complete",
DEFAULT 2026-02-13T16:44:38.790678Z "overall_confidence": "high",
DEFAULT 2026-02-13T16:44:38.790681Z "executive_summary": {
DEFAULT 2026-02-13T16:44:38.790685Z "headline": "Wind Composites Market Surges Toward $4.5B in 2026 as Global Installations Hit 150 GW Record",
DEFAULT 2026-02-13T16:44:38.790688Z "key_metrics": [
DEFAULT 2026-02-13T16:44:38.790697Z {"label": "Global Wind Installations (2025)", "value": "150 GW", "context": "Record third consecutive year, per GWEC — directly drives composite demand"},
DEFAULT 2026-02-13T16:44:38.790703Z {"label": "Wind Energy Composites Market (2024)", "value": "$4.10B", "context": "Projected to reach $6.12B by 2031 at 5.90% CAGR"},
DEFAULT 2026-02-13T16:44:38.790708Z {"label": "Carbon Fiber Composites Market (2026)", "value": "$24.67B", "context": "Up from $23.27B in 2025, wind blades a primary demand driver"},
DEFAULT 2026-02-13T16:44:38.790713Z {"label": "TPI Composites FY2025 Guidance", "value": "$1.4-1.5B", "context": "14.3% Q1 YoY growth with 80-85% utilization across 34 lines"},
DEFAULT 2026-02-13T16:44:38.790718Z {"context":"Sustainable through 2030 per S&P Global industry analysis", "label":"Epoxy Resin Demand Growth (Wind)", "value":"15-18% YoY"}
DEFAULT 2026-02-13T16:44:38.790722Z ],
DEFAULT 2026-02-13T16:44:38.790725Z "key_points": [
DEFAULT 2026-02-13T16:44:38.790729Z "GWEC reports record 150 GW of global wind installations in 2025, with China contributing 100 GW and India 6.3 GW, sustaining composite demand into 2026.",
DEFAULT 2026-02-13T16:44:38.790732Z "The carbon fiber composites market is projected to reach $24.67 billion in 2026, up 6% from $23.27 billion in 2025, per Precedence Research.",
DEFAULT 2026-02-13T16:44:38.790736Z "TPI Composites posted 14.3% Q1 2025 revenue growth to $336.2M and targets $2B+ wind revenue potential within existing 34-line manufacturing capacity.",
DEFAULT 2026-02-13T16:44:38.790739Z "Wind energy is driving 15-18% annual growth in epoxy resin demand through 2030, creating unprecedented specialty chemical demand per S&P Global analysis.",
DEFAULT 2026-02-13T16:44:38.790743Z "Nordex SE achieved record 10.2 GW of wind turbine orders in 2025, signaling robust OEM backlogs that will translate to composite material purchases in 2026.",
DEFAULT 2026-02-13T16:44:38.790746Z "Vestas is doubling pro
DEFAULT 2026-02-13T16:44:38.790750Z 2026-02-13 16:44:38,789 - app.agents.research.synthesizer - ERROR - [SYNTHESIZER] Output data keys: ['report_id', 'generated_at', 'query', 'data_completeness', 'overall_confidence', 'executive_summary', 'sections', 'thinking_content', 'all_visuals', 'companies_with_logos', 'sources_used', 'source_breakdown', 'data_gaps', 'warnings', 'research_time_seconds', 'field_sales']
DEFAULT 2026-02-13T16:44:38.790754Z 2026-02-13 16:44:38,789 - app.agents.research.synthesizer - WARNING - [SYNTHESIZER] Generated FALLBACK report due to parsing error
DEFAULT 2026-02-13T16:44:38.831627Z 2026-02-13 16:44:38,829 - app.utils.resilient_llm - INFO - Initialized resilient LLM: claude-haiku-4-5 (Anthropic) -> gemini-2.5-flash (Gemini, max_tokens=4096)
DEFAULT 2026-02-13T16:44:38.832010Z 2026-02-13 16:44:38,830 - app.utils.resilient_llm - INFO - Async invoking primary model: claude-haiku-4-5 (message count: 2)
DEFAULT 2026-02-13T16:44:43.925749Z 2026-02-13 16:44:43,923 - app.utils.resilient_llm - INFO - Primary model (claude-haiku-4-5) succeeded in 5.09s
DEFAULT 2026-02-13T16:44:43.925932Z 2026-02-13 16:44:43,923 - app.agents.research.validator - WARNING - Validator failed: 3 issues, 3 unsubstantiated claims
DEFAULT 2026-02-13T16:44:43.925940Z 2026-02-13 16:44:43,924 - app.agents.research.validator - INFO - Validator Agent completed in 5.13s
DEFAULT 2026-02-13T16:44:43.932721Z 2026-02-13 16:44:43,930 - app.api.routes.deep_research - INFO - Cached report for query hash: fdaaf2c9f798c441
DEFAULT 2026-02-13T16:44:43.932732Z 2026-02-13 16:44:43,930 - app.api.routes.deep_research - INFO - Cached research report (memory): hash=fdaaf2c9f798c441, query='what is the outlook for the wind and wind energy c...'
DEFAULT 2026-02-13T16:44:44.316458Z 2026-02-13 16:44:44,314 - app.db.gcp_storage - INFO - Stored deep research report bbb91cd1-b681-4454-afc8-30936f7a3bdf: what is the outlook for the wind and wind energy c...
DEFAULT 2026-02-13T16:44:44.316471Z 2026-02-13 16:44:44,314 - app.agents.research.memory - INFO - Stored research report bbb91cd1-b681-4454-afc8-30936f7a3bdf (hash: fdaaf2c9f798c441)
DEFAULT 2026-02-13T16:44:44.316476Z 2026-02-13 16:44:44,314 - app.api.routes.deep_research - INFO - Persisted research report (BigQuery): id=bbb91cd1-b681-4454-afc8-30936f7a3bdf
DEFAULT 2026-02-13T16:48:58.552361Z INFO: 169.254.169.126:39745 - "GET /health HTTP/1.1" 200 OK
