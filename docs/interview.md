# AI 智能客服项目面试手册

> 每个问题都包含 **30 秒面试回答** + **深入追问** + **结合本项目代码的回答**。
> 
> 不要背诵整篇文档。重点看"结合代码回答"部分——面试官会追问到具体实现细节。

---

## 目录

- [项目整体](#一项目整体)
- [RAG](#二rag)
- [Agent](#三agent)
- [SSE](#四sse)
- [工程化](#五工程化)
- [性能](#六性能)
- [安全](#七安全)
- [故障处理](#八故障处理)

---

## 一、项目整体

### Q1：介绍一下你的智能客服项目。

**30 秒回答**
> 我做了一个企业级 AI 智能客服系统，前后端分离架构。后端 FastAPI + SQLite + RAG + Agent Router + Tool Calling，前端 Vue3 + Vite。核心能力是：自动识别用户问题类型（闲聊/查订单/问知识库/要人工），路由到对应处理链路，用 SSE 流式输出给前端。做了本地 Embedding 避免云端依赖，Request ID 全链路追踪，Docker 一键部署。

**深入追问**
> - 和其他 AI 客服项目的区别？
> - 你做了哪些别人没做的？
> - 最有技术含量的部分是什么？

**结合代码回答**
> 区别在于我没有用 LangChain 或 Dify 这类框架，全部自己实现——Router、Orchestrator、VectorStore、Embedding 降级链路都是自研。核心亮点是 Agent Router + Tool Orchestrator 双层设计（router.py 只管路由决策，orchestrator.py 管多步 Tool 编排），以及 8 种事件类型的 SSE 协议（比单一 message 流信息密度高很多）。

---

### Q2：项目整体架构是什么？

**30 秒回答**
> 分层架构：API 层（auth/chat/conversations/kb 路由）→ Service 层（chat_service/agent.router/agent.orchestrator/rag.* /tools.*）→ Models + Schemas + DB。后端收到请求 → Agent Router 决策 → RAG 检索或 Tool 调用或正常 LLM → SSE 流式返回。

**深入追问**
> - 为什么不把所有逻辑放 main.py？
> - 每个层的职责边界？
> - 这样分层带来了什么好处？

**结合代码回答**
> 原来就是单体 main.py，有 800+ 行。重构后 app/api/ 只做 HTTP 路由 + 依赖注入 + 异常捕获；app/services/ 做业务逻辑，不感知 HTTP，可以单测；app/core/ 放 config 和 security。好处是 P5.3 做 8 场景测试时，只测 service 层就能验证核心逻辑，不用每次都走 HTTP。

---

### Q3：为什么前后端分离？

**30 秒回答**
> 独立迭代、独立部署。后端 SSE 流式在 FastAPI StreamingResponse 里天然支持，JWT 鉴权清晰；前端用 Vue Router lazy loading + AbortController 做停止生成按钮，交互体验比 SSR 好。

**深入追问**
> - 前后端怎么通信？
> - CORS 怎么处理？
> - 生产环境怎么部署？

**结合代码回答**
> 开发时 Vite 代理 `/api` → `http://127.0.0.1:8000` 并剥离前缀（vite.config.js proxy 配置）；生产 Nginx 反代，SSE 路径单独关 proxy_buffering。CORS 目前允许 `*`，生产要收紧到前端域名。

---

### Q4：为什么用 Vue3 + FastAPI？

**30 秒回答**
> Vue3 Composition API 比 Options API 好组织复杂状态，Chat.vue 里 streaming 状态、Tool 步骤、Request ID 这些用 ref/reactive 很清晰。FastAPI 原生支持 StreamingResponse 做 SSE，Pydantic 自动校验请求参数，SQLAlchemy ORM 操作数据库比手写 SQL 安全。

**深入追问**
> - 为什么不用 React？
> - 为什么不用 Flask/Django？
> - 选型过程中对比过什么？

**结合代码回答**
> 选 Vue3 是因为 Element Plus 表单/表格组件成熟，项目里有分类管理、知识库管理等后台页面，Element Plus 能省很多事。FastAPI 选它是因为 Pydantic v1 + StreamingResponse 组合，SSE 只需要 `yield f"event: message\ndata: {json}\n\n"` 就行，不像 Flask-SSE 还要装额外包。

---

## 二、RAG

### Q5：什么是 RAG？

**30 秒回答**
> Retrieval-Augmented Generation，检索增强生成。在 LLM 回答前先从知识库检索相关片段，把检索结果作为 context 喂给 LLM，让它基于已知信息回答，而不是凭空生成。好处是减少幻觉、能回答最新问题、能带来源（cite）。

**深入追问**
> - 为什么不用 fine-tuning？
> - RAG 和 fine-tuning 各适合什么场景？
> - 你做的 RAG 和 LangChain 里的有什么区别？

**结合代码回答**
> 我没有用 LangChain，直接实现了 Pipeline：Query → Embedding（embedder.py）→ VectorStore 检索（vector_store.py 的 query 方法）→ 阈值过滤 → Citation → 拼进 system prompt（rag_service.py 的 build_rag_system_prompt）。Threshold 0.45 是反复测试定的。

---

### Q6：为什么使用 Embedding？

**30 秒回答**
> LLM 不能直接"搜索"知识库里的文本。Embedding 把文本映射成向量空间里的点，语义相似的文本向量距离近。用户问"退货规则"，向量检索找到"7天无理由退款"那段，比关键词搜索准得多。

**深入追问**
> - Embedding 怎么生成？
> - 向量怎么比较相似度？
> - 为什么不用 BM25 关键词检索？

**结合代码回答**
> 用 cosine 余弦相似度（vector_store.py 的 `_cosine` 静态方法）。BGE 输出已经 L2 归一化了，所以 cosine 就是 dot product。BM25 关键词匹配在客服场景下不够——用户问"东西不想要了能退吗"和知识库里的"7天无理由退款"关键词几乎重叠，但语义是一样的。

---

### Q7：为什么从智谱 Embedding 改成本地 BGE？

**30 秒回答**
> 三个原因：一是智谱 Embedding 也要 API Key，多一份配置多一个故障点；二是网络依赖，离线或网络差时整个 RAG 链都挂了；三是数据安全，用户知识库内容要发到云端做向量化。换本地 BGE 之后，模型下载一次就常驻内存，< 10ms 就能出向量，成本为零。

**深入追问**
> - 迁移过程遇到什么坑？
> - 不同模型的向量能混用吗？
> - 怎么处理旧向量？

**结合代码回答**
> 最大的坑是**旧向量不能混用**——hash embedder 是 256 维，BGE 是 512 维，VectorStore 里已经存的 256 维向量和新生成的 512 维向量没法一起做余弦相似度。所以迁移时要**全量重建 VectorStore**：删掉旧 JSON，从 DB 里读 DocumentChunk 内容，用新模型重新 embed 再 upsert。项目里有 rebuild_vectorstore.py 脚本。

---

### Q8：BGE-small-zh-v1.5 是什么？

**30 秒回答**
> 北京智源人工智能研究院发布的中文 Embedding 模型，small 版本是 512 维，适合中文场景。比英文模型好很多，因为中文的语义边界和英文不一样。

**深入追问**
> - 512 维和 1024 维有什么区别？
> - 为什么选 small 而不是 base/large？
> - 怎么加载？

**结合代码回答**
> 用 sentence-transformers 加载（embedder.py 的 LocalEmbedder 类）。small 是 512 维，base 是 768 维，large 是 1024 维。选 small 是因为启动快、内存占用小（~100MB），在客服场景下效果够用。首次加载会自动从 HuggingFace 下载到 `~/.cache/huggingface/hub/`，之后完全离线。

---

### Q9：向量检索怎么做？

**30 秒回答**
> 用户问题 → BGE Embedding 成 query 向量 → 遍历 VectorStore 里所有 chunk 向量算余弦相似度 → 排序取 top_k → 过滤掉低于阈值的 → 剩下的作为 context + citation 喂给 LLM。

**深入追问**
> - top_k 怎么定的？
> - 向量很多时怎么办？
> - 为什么不用 FAISS/Chroma？

**结合代码回答**
> top_k 默认 5（config.py 的 RAG_TOP_K）。自建 VectorStore 用纯 Python 余弦检索（vector_store.py query 方法），当前知识库只有几百 chunks，遍历一次毫秒级。为什么不用 Chroma？因为 Chroma 会强制升级 fastapi 版本，从项目记忆里看到这个坑。VectorStore 是抽象接口，以后数据量大了可以无缝替换。

---

### Q10：similarity threshold 为什么是 0.45？

**30 秒回答**
> 太低会把不相关的片段喂给 LLM，污染 context；太高会漏掉正确答案。0.45 是反复测试的平衡点——BGE 在中文客服场景下，正确命中的相似度通常在 0.5~0.8 之间，0.45 是下限。

**深入追问**
> - 调过哪些值？效果怎么样？
> - 不同模型的阈值一样吗？

**结合代码回答**
> 调过 0.2、0.3、0.4、0.45、0.5、0.7。0.2 时很多不相关片段混进来，LLM 答得不知所云；0.7 时明明有答案的问题也检索不到。BGE 512 维的阈值和别的模型不一样——如果换 bge-large 或者换英文模型，这个阈值要重新调。

---

### Q11：citation 从哪里来的？

**30 秒回答**
> 全部来自向量检索结果。检索时每条 chunk 都带着 metadata（文件名、文档 ID、chunk 序号），命中后直接把这些信息作为 citation 事件通过 SSE 发给前端，前端在 AI 回复下方展示参考来源。

**深入追问**
> - 会不会伪造 citation？
> - citation 不准确怎么办？

**结合代码回答**
> 绝对不伪造。citation 的每个字段都来自 VectorStore query 结果的 metadata。如果阈值过滤后没有命中，就不发 citation 事件。这点是 P5.1 审查时特意检查的——不能为了"看起来专业"给 LLM 随便编来源。

---

### Q12：Embedding 失败怎么办？

**30 秒回答**
> 三级降级：Local BGE 失败 → 换 OpenAI 兼容 Embedding（如果配了 Key）→ 再失败 → 最终 fallback 到 hash-3gram-256（字符 3-gram feature hashing，纯 Python，零依赖）。hash 没有语义能力，但保证系统不会因为 Embedding 挂了而完全不能用。

**深入追问**
> - hash-3gram 具体怎么实现？
> - 降级后 RAG 还能用吗？

**结合代码回答**
> embedder.py 里的 HashEmbedder 类：把文本按字符切成 3-gram，每个 gram 用 hash 映射到 256 维向量，计数作为特征。降级后 RAG 还能跑（不会报错），但相似度会非常低（通常负的），所以 RAG 路由会 fallback 到 normal_chat。这就是 P5.3 开始时 RAG 全部走 normal_chat 的原因——当时 sentence-transformers 没装，BGE 加载失败走了 hash，top_score=-0.04。

---

## 三、Agent

### Q13：Agent Router 是干什么的？

**30 秒回答**
> 在调用 LLM 之前，先判断用户问题应该走哪条处理链路。5 条路由：human_service（要人工）、chitchat（闲聊）、Tool 路由（查订单/物流）、RAG 路由（知识库）、normal_chat（默认）。每条路由优先级不同。

**深入追问**
> - Router 的输入输出是什么？
> - RouteDecision 包含哪些字段？

**结合代码回答**
> 输入是用户问题文本，输出是 RouteDecision 对象（router.py 里的 dataclass），包含 route、intent、rag_probe 等字段。prepare_agent_plan 函数同时做路由决策和 RAG Probe——不管最终路由是什么，都会先试一次 Embedding 检索，看看相似度够不够。

---

### Q14：Router 为什么没有直接让 LLM 决策？

**30 秒回答**
> 三个原因：延迟（LLM 路由一次 500ms~2s，规则 + RAG Probe 只要 50~100ms）；可预测（规则是确定性的，方便 debug）；省钱（DeepSeek 402 余额不足时，规则路由完全不受影响）。

**深入追问**
> - 有没有想过规则路由覆盖不了边界 case？
> - 规则写错了怎么办？

**结合代码回答**
> 确实有边界 case。比如用户说"订单10001退款"——同时有订单关键词和售后关键词。当前优先级是 Tool 优先于 RAG，所以走 order_query，再由 Orchestrator 决定要不要继续调退款相关。规则都写在 router.py 里，加一条关键词或改优先级很方便，不需要改 LLM prompt。

---

### Q15：Tool Calling 怎么实现？

**30 秒回答**
> 自研 Tool Registry 模式。每个 Tool 是一个 Python 函数，统一返回 `{ok: bool, data: dict, error: str | None}` 结构。Orchestrator 负责编排——调用 Tool、判断结果、决定要不要继续、收集历史喂给 LLM。

**深入追问**
> - 和 LangChain 的 Tool 有什么区别？
> - Tool 的参数怎么传？

**结合代码回答**
> 区别在于参数传递——我不让 LLM 从自然语言里解析 Tool 参数（那会错）。而是 Router 已经识别出"查订单"，Order ID 从用户输入里用正则提取。Tool 收到的是结构化参数（order_id="10001"），不是 LLM 生成的 function call JSON。Tool 结果也是结构化 JSON，直接喂给下一个 Tool 或 LLM 当 context。

---

### Q16：Tool Registry 是干什么的？

**30 秒回答**
> 所有 Tool 的注册中心。每个 Tool 在 Registry 里注册自己的名字、处理函数、参数提取逻辑。Orchestrator 通过名字查到 Tool 然后调用。

**深入追问**
> - 为什么不直接 import 调用？
> - Registry 里有哪些 Tool？

**结合代码回答**
> 现在只有两个 Tool：order_tool.py 和 logistics_tool.py。注册中心让扩展新 Tool 很容易——写个新文件、在 registry.py 里注册就行。Orchestrator 遍历 registered_tools 按路由匹配。

---

### Q17：Orchestrator 为什么单独拆出来？

**30 秒回答**
> Router 只管"用什么能力"（order_query 还是 logistics_query），不管"怎么串起来"。编排逻辑（fail-fast、链式调用、收集历史）是另外一个关注点，单独一层避免 chat.py 变成一堆 if/else 泥球。

**深入追问**
> - Orchestrator 和 Router 的接口是什么？
> - Orchestrator 失败了怎么办？

**结合代码回答**
> Router 返回 RouteDecision（告诉 Orchestrator "要调用哪些 Tool"），Orchestrator 接收决策后执行 Tool、管理调用历史、组装 LLM context。Orchestrator 内部有 try/except，任何 Tool 异常都会 emit error 事件但不打断 SSE 到 done。

---

### Q18：多步 Tool 怎么实现？

**30 秒回答**
> Orchestrator 一个循环，最多 MAX_TOOL_STEPS=3 次迭代：取 Tool → 执行 → 记录历史 → 判断要不要继续（fail-fast 条件）→ 决定下一个 Tool。最终把整个 Tool 历史作为结构化 JSON 喂给 LLM。

**深入追问**
> - 怎么决定继续还是停止？
> - Tool 结果怎么传递给下一个 Tool？

**结合代码回答**
> 停止条件有三个：MAX_TOOL_STEPS 到了、上一个 Tool ok=false、order_query 返回 not_found / 没有 tracking_no。继续条件只有一个：上一个 Tool 成功且包含下一个 Tool 所需的数据（比如 order_query 返回 tracking_no，Orchestrator 自动把它传给 logistics_query）。

---

### Q19：为什么 order_query 后可以自动调用 logistics_query？

**30 秒回答**
> 这是 Orchestrator 里的链式规则：如果第一个 Tool 是 order_query 且成功返回了 tracking_no，就自动追加 logistics_query 到待执行队列。参数从 order_query 结果里提取，不用再等 LLM 决策。

**深入追问**
> - 这不是硬编码吗？
> - 如果以后有更多链式组合怎么办？

**结合代码回答**
> 是的，当前链式规则是硬编码在 Orchestrator 里的。但接口留好了——每个 Tool 可以声明自己的 "followup" 条件。未来加新的链式组合（比如 order_query → refund_query）只要在对应 Tool 里加声明，Orchestrator 的主循环不用改。

---

### Q20：fail-fast 是怎么设计的？

**30 秒回答**
> Tool 执行前检查前一个 Tool 的结果：如果 ok=false 或返回 not_found 或缺少后续 Tool 必需的字段（比如 tracking_no），立即停止，emit tool_result + done，不浪费时间调下一个 Tool。

**深入追问**
> - 为什么不继续调用让下一个 Tool 自己失败？
> - fail-fast 对用户体验有什么好处？

**结合代码回答**
> 如果不 fail-fast，用户查一个不存在的订单，要等 order_query 返回 not_found → 再调 logistics_query（因为 Router 里有"物流"关键词）→ 物流 Tool 查不到 tracking_no → 返回错误。两次 Tool 调用 + LLM 两次，多花 3~5 秒。fail-fast 直接一次调用就结束，响应快很多。

---

### Q21：MAX_TOOL_STEPS 为什么是 3？

**30 秒回答**
> 防止无限 Tool 循环（比如 Tool A 调 Tool B，Tool B 又调 Tool A）。3 步足够覆盖客服场景的链式查询（查订单 → 查物流 → 查退款状态）。如果超过 3 步还没得出结论，大概率是 Tool 设计有问题，应该返回错误让用户确认。

**深入追问**
> - 改成 5 会怎么样？
> - 这个值在哪里配置？

**结合代码回答**
> 在 config.py 里。设成 3 是因为当前只有两个 Tool，一个链式最多 2 步，3 步是安全余量。如果以后加更多 Tool 链式组合，可以调高。为什么不设大？多一步 Tool 调用多 1~2 秒延迟，对客服来说响应速度比"能调更多 Tool"重要。

---

## 四、SSE

### Q22：为什么使用 SSE？

**30 秒回答**
> LLM 流式输出（逐 token 生成），SSE 让前端实时收到每个 token 并立即展示，不用等整段生成完。比一次性返回整段体验好太多——用户看到 "正在思考..." → "退款" → "政策" → "是" →... 的逐字效果。

**深入追问**
> - SSE 和轮询比呢？
> - 有没有考虑过 WebSocket？

**结合代码回答**
> SSE 和轮询比，SSE 是服务器主动推送，没有轮询延迟和无效请求。比 WebSocket 简单——SSE 是 HTTP 单向推送，协议就是 `event: xxx\ndata: xxx\n\n`，Nginx 只需要关 proxy_buffering 就能透传。WebSocket 是双向，本项目不需要前端主动推流，SSE 够用了。

---

### Q23：SSE 和 WebSocket 有什么区别？

**30 秒回答**
> 三个核心区别：SSE 是 HTTP 长连接、单向（服务器→客户端）、自动重连；WebSocket 是独立协议、双向、需要应用层重连。SSE 可以通过 Nginx 反代，WebSocket 需要专门的 upgrade 配置。

**深入追问**
> - 什么时候该用 WebSocket 而不是 SSE？
> - SSE 有什么限制？

**结合代码回答**
> 当需要双向实时通信时（比如协同编辑、实时游戏）才用 WebSocket。SSE 的限制是只能单向、浏览器并发连接数有限（Chrome 对同域名限 6 个）。但客服场景下并发不会那么大，这个限制可以接受。

---

### Q24：SSE 断开怎么办？

**30 秒回答**
> 前端用 EventSource API，浏览器会自动重连。后端 Generator 的 finally 块里保存已生成的内容——即使客户端中途断开，已经生成的回复也会落到数据库。

**深入追问**
> - 重连后能续上吗？
> - 服务端怎么知道客户端断了？

**结合代码回答**
> 当前没有续传机制——客户端重连后要重新发起 /chat 请求。Generator 里捕获 GeneratorExit 异常（FastAPI 在客户端断开时会关闭迭代器），finally 块里执行 `_persist_chat` 保存已生成的完整回复。所以即使断了，刷新页面后历史记录里已经有了完整回复。

---

### Q25：为什么前端需要 AbortController？

**30 秒回答**
> 让用户能主动"停止生成"。点停止按钮时 abort()，前端 catch 到 AbortError 后显示友好提示，后端 Generator 收到 GeneratorExit 后在 finally 里保存已生成内容。

**深入追问**
> - 不 abort 会怎么样？
> - abort 后后端还在跑吗？

**结合代码回答**
> 不 abort 的话用户只能等 LLM 生成完——如果用户发现问题问错了，或者 LLM 在胡说，只能干等。abort 后 Generator 立即停止（Python 的 GeneratorExit 是异步异常），后端不会继续消耗 LLM tokens。

---

### Q26：为什么 Nginx 必须关闭 proxy_buffering？

**30 秒回答**
> Nginx 默认会缓冲上游响应，攒够一批再发给客户端。SSE 是逐 chunk 推送，如果被 Nginx 缓冲，浏览器收不到逐字效果，会等很久才一下子冒出来。关了 proxy_buffering 才能让 chunk 实时透传。

**深入追问**
> - 还有什么 Nginx 配置需要调？
> - 为什么要设 read_timeout 3600s？

**结合代码回答**
> 还需要 proxy_cache off（SSE 不能缓存）、proxy_set_header Connection ""（清除 hop-by-hop headers）、chunked_transfer_encoding on。read_timeout 设 3600s 是因为 LLM 流式可能持续很久——如果 Nginx 默认 60s 超时，SSE 连接就断了。

---

### Q27：LLM 流式异常怎么办？

**30 秒回答**
> 流式中途如果 LLM 断了（网络超时、402 余额不足），会 catch 到异常，emit error 事件告知前端，然后 emit done 结束流。已生成的内容仍然正常落库。

**深入追问**
> - error 事件里有什么信息？
> - 前端怎么处理 error 事件？

**结合代码回答**
> error 事件里有 code 和 message。前端收到 error 后在 AI 气泡上显示红色提示（比如"AI 回复中断，请稍后重试"），但不会卡住——done 事件还是会来，流正常结束。

---

## 五、工程化

### Q28：Request ID 是干什么的？

**30 秒回答**
> 全链路追踪。每个请求进入时生成一个唯一 ID，贯穿 Router → RAG → Tool → LLM → 落库的所有日志。排查问题时 grep 这个 ID 就能看到完整调用链。

**深入追问**
> - 怎么传递的？
> - 和 Trace ID / Span ID 有什么区别？

**结合代码回答**
> 用 ASGI 中间件 + contextvars。中间件从请求头 X-Request-ID 读（客户端透传）或生成新的 UUID，写入 contextvars。日志 Filter 里从 contextvars 读 request_id 自动加到每条日志上。响应头回写 X-Request-ID。

---

### Q29：contextvars 为什么适合 Request ID？

**30 秒回答**
> FastAPI/Starlette 每个请求在同一个 asyncio Task 里执行。contextvars 是 Python 原生的"请求级全局变量"，自动在 Task 上下文里传递，不需要每个函数手动传 request_id 参数。asyncio.create_task 会自动拷贝 contextvar 值。

**深入追问**
> - 和 thread-local 变量比呢？
> - 有没有可能 Request ID 泄漏到其他请求？

**结合代码回答**
> Thread-local 在多线程环境下不安全（Python 的 GIL 但异步用的是协程）。contextvars 是协程安全的——每个 asyncio Task 有独立的 context，一个 Task 的 Request ID 不会泄漏到另一个。

---

### Q30：日志如何做到不泄露 API Key？

**30 秒回答**
> 三层防护：一是敏感信息（API Key、Secret、密码）**绝对不**写进日志内容；二是 logging Filter 里做脱敏扫描，如果有人不小心记了 Key 也会被替换成 `***`；三是配置状态只记 `configured=true/false`，不记实际值。

**深入追问**
> - 如果 Key 在请求头里怎么办？
> - 脱敏规则是什么？

**结合代码回答**
> Authorization header 里的 token 在日志里会被截断或替换。DEEPSEEK_API_KEY 即使在 config 里有值，日志里也只显示 `llm_configured: true`，绝不显示 Key 前几位。

---

### Q31：Docker 怎么部署？

**30 秒回答**
> docker compose up -d --build 一键启动。两个服务：backend（FastAPI + Uvicorn）、frontend（Nginx 反代 + 静态文件）。4 个 Volume 持久化 SQLite、Uploads、VectorStore、HF Cache。

**深入追问**
> - 为什么用两个 Dockerfile？
> - 端口怎么映射？

**结合代码回答**
> 两个 Dockerfile 是因为技术栈完全不同——后端 Python + CPU torch，前端 Node + Nginx 静态服务。backend 容器监听 8000，前端 Nginx 监听 80（开发映射到 3000），Nginx 把 /api/ 代理到 backend:8000。

---

### Q32：Docker 数据为什么需要 Volume？

**30 秒回答**
> Docker 容器重建时，文件系统里的数据会丢失。SQLite chat.db 丢了就是所有用户数据；VectorStore 丢了要重新 Embedding（几分钟）；HF Cache 丢了要重新下载 BGE 模型（300MB+，受网络影响）。所以这四个目录必须持久化到宿主机。

**深入追问**
> - 为什么不用 bind mount？
> - 4 个 Volume 分别挂什么路径？

**结合代码回答**
> 我用的就是 bind mount（compose 文件里 `./data/sqlite:/app/data/sqlite`）。Docker named volume 和 bind mount 都能持久化，bind mount 更直观——宿主机上看得到文件结构。

---

### Q33：Embedding 模型为什么要持久化？

**30 秒回答**
> BGE-small-zh-v1.5 大约 300MB，首次下载受 HuggingFace 网络速度影响可能要几分钟。每次容器重建都重新下载很痛苦。而且离线加载更快——模型缓存在本地时，sentence-transformers 几秒就能加载完；重新下载要等网络。

**深入追问**
> - HF_HUB_OFFLINE=1 是干什么的？
> - 模型更新了怎么办？

**结合代码回答**
> HF_HUB_OFFLINE=1 让 sentence-transformers 只读本地缓存，不尝试联网。设置后启动时不依赖网络。模型更新时删掉 ./data/hf_cache 目录让它重新下载就行。

---

### Q34：Docker 为什么使用非 root 用户？

**30 秒回答**
> 安全基线。如果容器里运行的应用被攻击，攻击者拿到的是非 root 权限，对宿主机的破坏力更小。Docker Hub 上大部分官方镜像都建议非 root 运行。

**深入追问**
> - 怎么创建非 root 用户？
> - 非 root 用户权限不够怎么办？

**结合代码回答**
> 后端 Dockerfile 里 `RUN groupadd -r appuser && useradd -r -g appuser appuser && chown -R appuser /app`，最后 `USER appuser`。非 root 可以正常读写 bind mount 的 Volume（因为 Docker 会把 Volume 的权限映射好）。

---

## 六、性能

### Q35：P5.2 做了什么性能优化？

**30 秒回答**
> 前端三件套：Router lazy loading（`() => import()`）、highlight.js core-only（从 900kB 减到 20kB）、manualChunks（按 Element Plus / highlight / marked 分离）。最终产物从单 chunk 2058kB 减到 12 chunks 共 66kB（97% 减包）。

**深入追问**
> - 后端有没有性能优化？
> - 怎么衡量优化效果？

**结合代码回答**
> 后端没做"优化"，因为 P5.1 审查时发现已经够快——BGE 本地 Embedding < 10ms，纯 Python 余弦检索 ms 级。如果数据量大了再考虑换 FAISS/Chroma。前端优化效果可以量化：npm run build 的产物大小对比。

---

### Q36：为什么不能简单提高 chunkSizeWarningLimit？

**30 秒回答**
> chunkSizeWarningLimit 只是让 Vite 不警告，但大 chunk 该慢还是慢——浏览器下载一个 2MB 的 chunk 比下载 12 个 100kB 的 chunk 慢得多，而且无法并行加载。提高 limit 是自欺欺人。

**深入追问**
> - 那正确的做法是什么？
> - 你做了什么替代方案？

**结合代码回答**
> 正确做法是拆 chunk——Router lazy loading（不同路由的代码分 chunk，按路由加载）、manualChunks（把 Element Plus、highlight.js、marked 这些大依赖拆成独立 chunk，浏览器可以并行下载）。highlight.js 换 core-only 版本从源头减体积。

---

### Q37：lazy loading 有什么作用？

**30 秒回答**
> 页面代码按需加载。用户第一次打开只加载登录页的代码，进入聊天页才加载 Chat.vue，不把整个应用塞到首屏。首屏 JS 从 2058kB 降到只需要加载 Login 相关的几 kB。

**深入追问**
> - 懒加载怎么实现？
> - 和 preload/prefetch 的区别？

**结合代码回答**
> Vue Router 里用 `() => import('./views/Chat.vue')` 而不是直接 `import Chat from './views/Chat.vue'`。Vite 构建时会把 Chat.vue 单独打成一个 chunk，运行时按需 fetch。

---

### Q38：manualChunks 解决了什么问题？

**30 秒回答**
> 默认情况下 Vite 会把所有东西打进一个 chunk。manualChunks 告诉它把 Element Plus、highlight.js、marked 这些大依赖拆成独立 chunk。好处：一是浏览器可以并行下载；二是如果用户没用到 highlight.js（比如 Markdown 代码块少），可以不加载这个 chunk。

**深入追问**
> - manualChunks 怎么配置？
> - 会不会产生过多小 chunk？

**结合代码回答**
> vite.config.js 里：
> ```js
> manualChunks: {
>   'element-plus': ['element-plus'],
>   'highlight': ['highlight.js'],
>   'marked': ['marked'],
> }
> ```
> 拆了 3 个大依赖包，加上自动拆分的 node_modules，总共 12 个 chunk——不会太多也不会太少。

---

## 七、安全

### Q39：JWT 怎么实现？

**30 秒回答**
> PyJWT 库，HS256 签名。登录时根据 username 生成 token（`{"sub": username, "exp": expire_time}`），有效期 24 小时。请求时 FastAPI Depends(get_current_user) 校验 token → 取 username → 查 DB → 返回 User 对象。

**深入追问**
> - HS256 和 RS256 有什么区别？
> - JWT 过期了怎么办？

**结合代码回答**
> HS256 是对称加密，RS256 是非对称（私钥签名、公钥验证）。HS256 适合单体应用，RS256 适合多服务验证。过期后前端 catch 到 401，自动跳登录页（axios 响应拦截器里）。

---

### Q40：如何防止 conversation 越权？

**30 秒回答**
> 每次访问会话前强制校验归属——`verify_conversation(db, conversation_id, current_user.id)` 返回 None 就说明不是你的会话或不存在，返回 404。

**深入追问**
> - 直接在 SQL 里加 WHERE user_id = ? 不行吗？
> - 还有哪些地方需要防越权？

**结合代码回答**
> 是的，SQL 里加 WHERE 也可以。但我选择在 service 层封装一个 verify 函数，API 层每次调它——这样所有会话相关的路由都用同一个校验逻辑，不会有漏掉的路由。知识库文档也需要按 user_id 过滤（不过当前 demo 只有一个 KB，所以没做）。

---

### Q41：Markdown XSS 怎么处理？

**30 秒回答**
> 轻量方案：在渲染前过滤掉 `<script>` 标签和 `on*=` 事件属性。因为是 LLM 生成的 Markdown，恶意注入风险较低，不需要 DOMPurify 这种重量级方案。

**深入追问**
> - 为什么不直接用 DOMPurify？
> - 还有哪些 XSS 风险点？

**结合代码回答**
> DOMPurify 要引一个几百 KB 的前端包，对 demo 来说性价比不高。如果以后要开放用户自定义 Markdown（比如用户自己上传的文档内容），就必须上 DOMPurify。其他风险点：链接的 javascript: 协议、iframe 标签——当前也拦了。

---

### Q42：SECRET_KEY 默认值为什么有风险？

**30 秒回答**
> 如果用硬编码的默认值，攻击者猜到默认值就能伪造任意用户的 JWT token。所以项目启动时如果检测到默认值，会打 WARNING 日志并在 /health 接口里标记出来，提醒生产必须替换。

**深入追问**
> - 怎么检测默认值？
> - 生产怎么管理 Secret？

**结合代码回答**
> main.py 里有个检查：如果 SECRET_KEY 等于占位值（比如 "CHANGE_ME_IN_PRODUCTION"），就 logger.warning。生产应该从环境变量读（.env 里配好），而且 .env 要进 .gitignore。

---

### Q43：.env 为什么不能提交 Git？

**30 秒回答**
> .env 里存了 DeepSeek API Key、JWT Secret 等敏感信息。提交 Git 等于公开暴露，任何人拿到仓库就能调用你的 LLM 额度、伪造用户 token。.env.example 是安全的——只有占位符，没有真实 Key。

**深入追问**
> - 如果不小心提交了怎么办？
> - 还有什么文件不能提交？

**结合代码回答**
> 不小心提交了要立即 revoke（在 DeepSeek 后台换 Key，重新生成 JWT Secret）并 force push 覆盖 git history。其他不能提交的：chat.db（用户数据）、vector_store/（Embedding 数据）、uploads/（用户上传的文件）、.venv/、node_modules/。

---

## 八、故障处理

### Q44：DeepSeek 402 怎么处理？

**30 秒回答**
> 多层降级。LLM 调用失败时 catch 异常，走模板回复（按分类选预设文案，比如 normal_chat 就回复"这个问题我暂时无法准确回答，您可以描述更多细节..."）。SSE 协议不受影响——正常 emit message 再 emit done。

**深入追问**
> - 模板回复够不够用？
> - 怎么区分 402 和其他错误？

**结合代码回答**
> LLM 调用失败时不区分 402/网络超时/连接拒绝——统一走模板降级。因为用户不需要知道具体是什么错误，只要有回复就行。debug 时看日志能看到完整 traceback，但前端只收到友好的模板回复。

---

### Q45：RAG 知识库损坏怎么办？

**30 秒回答**
> VectorStore 文件损坏时，load 方法 catch JSONDecodeError 和 OSError，返回空的 items 列表。RAG 检索返回空结果，score 低于阈值，自动 fallback 到 normal_chat。系统不会因为一个 JSON 文件损坏而挂掉。

**深入追问**
> - 怎么触发重建？
> - DB 里的 chunks 会丢吗？

**结合代码回答**
> DB 里的 DocumentChunk 不会丢——VectorStore 是从 DB chunks 重新生成的。要重建的话，删掉 vector_store/kb_1.json，运行 rebuild_vectorstore.py 脚本（从 DB 读 chunks → BGE embed → 写回 VectorStore）。

---

### Q46：VectorStore JSON 损坏怎么办？

**30 秒回答**
> load 方法里 catch JSONDecodeError 和 OSError，返回空字典。query 返回空列表，RAG 自然 fallback 到 normal_chat。启动时不会报错，只是 RAG 暂时不可用。

**深入追问**
> - 有没有自动恢复机制？
> - 怎么检测损坏？

**结合代码回答**
> 当前没有自动恢复（自动重建太慢）。设计选择：**宁可 RAG 暂时不可用，也不让 /chat 500**。这是 P5.1 审查时特意要求的——任何 RAG 组件故障都不能导致主链路挂掉。手动恢复：删掉损坏的 JSON，跑 rebuild 脚本。

---

### Q47：DB 落库失败怎么办？

**30 秒回答**
> Generator 的 finally 块里 try/except 包裹落库逻辑。即使落库失败，SSE 也已经正常 emit done 了——用户端已经看到了完整回复。落库失败只打 error 日志，不影响用户体验。

**深入追问**
> - 为什么不让落库失败回滚整个对话？
> - 有没有重试？

**结合代码回答**
> 对话的价值是用户收到了 AI 的回复。落库只是为了以后看历史记录。如果因为落库失败就让用户重新发一遍，体验更差。所以设计选择是：**优先保证 SSE 正常结束，落库失败是次要问题**。没有重试——重试可能阻塞 finally 块导致 SSE 超时。

---

### Q48：Tool 调用失败怎么办？

**30 秒回答**
> Tool 内部 catch 所有异常，统一返回 `{ok: false, data: null, error: "错误信息"}`。Orchestrator 收到 ok=false 立即 fail-fast，停止后续 Tool 调用，把已有的 Tool 结果（哪怕只有一个失败的）和错误信息喂给 LLM，让它生成友好回复。

**深入追问**
> - 为什么不让 Tool 异常冒泡？
> - 怎么区分业务错误和系统错误？

**结合代码回答**
> 如果 Tool 异常冒泡到 Orchestrator，就会中断整个 SSE 流。所以每个 Tool 内部必须 try/except，错误转成结构化返回。业务错误（订单不存在）返回 ok=true 但 data 里 status=not_found，系统错误（SQL 挂了）返回 ok=false。Orchestrator 根据 ok 字段判断是否 fail-fast。

---

## 面试最后：给面试官看什么？

1. **运行后端**：`python -m uvicorn app.main:app` → 打开 `/docs` 看 Swagger UI
2. **运行前端**：`npm run dev` → 演示 8 个核心场景
3. **展示架构图**：README 里的 Mermaid 图
4. **展示测试结果**：verify_scenarios.py 的 8/8 PASS 输出
5. **展示 VectorStore**：`./data/vector_store/kb_1.json` 里是 BGE 512 维向量
6. **直接看代码**：router.py（Agent 路由）、orchestrator.py（Tool 编排）、embedder.py（三级降级）
7. **展示 Request ID**：日志里的 `request_id=xxx`，前端 DevTools 看 X-Request-ID 响应头

**诚实说清楚已知限制**（README 十四节）——面试官反而会欣赏工程判断力。
