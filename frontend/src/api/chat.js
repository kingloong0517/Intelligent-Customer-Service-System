/**
 * 聊天 & AI 分类 API
 * - AI 分类：POST /ai-classify
 * - 聊天：POST /chat （事件化 SSE：event: category/message/error/done，
 *   预留 rag/citation/tool_start/tool_result，通过 onEvent 统一接收）
 */
import request from '../utils/request'

/** AI 自动分类 */
export function aiClassify(userInput) {
  return request
    .post('/ai-classify', { user_input: userInput })
    .then((res) => res.data)
}

/**
 * 解析一条完整 SSE 事件块（"event: xxx\ndata: {...}"）并分发回调
 * @private
 */
function dispatchSseEvent(rawBlock, callbacks, state) {
  let event = 'message'
  const dataLines = []

  for (const line of rawBlock.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
  }
  if (!dataLines.length) return

  let data
  try {
    data = JSON.parse(dataLines.join('\n'))
  } catch {
    return // 非 JSON 载荷直接忽略
  }

  switch (event) {
    case 'message':
      callbacks.onMessage && callbacks.onMessage(data.content ?? '')
      break
    case 'category':
      callbacks.onCategory && callbacks.onCategory(data)
      break
    case 'rag':
      // RAG 路由结论：{used, reason, top_score, embedding_model, chunk_count}
      callbacks.onRag && callbacks.onRag(data)
      break
    case 'citation':
      // 知识库引用来源：{kb_id, document_id, filename, chunk_index, chunk_key, score, snippet}
      callbacks.onCitation && callbacks.onCitation(data)
      break
    case 'tool_start':
      // P5.2：Tool 开始执行，前端可展示状态提示
      // {tool: 'order_query', arguments: {...}}
      callbacks.onToolStart && callbacks.onToolStart(data)
      break
    case 'tool_result':
      // P5.2：Tool 执行完成，前端可展示状态提示
      // {tool: 'order_query', ok: true, data/error: ...}
      callbacks.onToolResult && callbacks.onToolResult(data)
      break
    case 'error':
      callbacks.onError && callbacks.onError(new Error(data.message || 'AI 服务异常'))
      break
    case 'done':
      state.doneReceived = true
      callbacks.onDone && callbacks.onDone(data)
      break
    default:
      callbacks.onEvent && callbacks.onEvent(event, data)
  }
}

/**
 * 发送聊天消息 → 事件化 SSE 流式响应
 * @param {object}   payload        {user_input, conversation_id, category}
 * @param {object}   callbacks
 *   onMessage(content) 拼接 AI 回复片段
 *   onCategory(data)   {category, intent}
 *   onRag(data)        RAG 路由结论
 *   onCitation(data)   知识库引用
 *   onToolStart(data)  Tool 开始 {tool, arguments}  P5.2 新增
 *   onToolResult(data) Tool 完成 {tool, ok, data/error}  P5.2 新增
 *   onError(err)       AI 服务错误
 *   onDone(data)       {message_id, conversation_id, request_id}
 *   onEvent(event,data)扩展事件
 * @param {AbortSignal} signal  外部取消信号
 * @returns {Promise<string>}    返回 X-Request-ID（供前端调试展示）
 */
export async function chatStream(payload, callbacks = {}, signal = null) {
  const token = localStorage.getItem('token')
  let requestId = ''

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify(payload),
      signal,
    })

    // P5.2：从响应头捕获 Request ID，用于前端调试展示
    requestId = response.headers.get('X-Request-ID') || ''
    callbacks.onRequestId && callbacks.onRequestId(requestId)

    if (!response.ok) {
      const text = await response.text()
      const err = new Error(text || '发送消息失败')
      callbacks.onError && callbacks.onError(err)
      throw err
    }

    const state = { doneReceived: false }
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    const consumeBlock = (raw) => {
      if (raw.trim()) dispatchSseEvent(raw, callbacks, state)
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      let sep
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        consumeBlock(buffer.slice(0, sep))
        buffer = buffer.slice(sep + 2)
      }
    }
    consumeBlock(buffer)

    // 兜底：服务端异常关闭未发 done 时，保证前端能结束 loading
    if (!state.doneReceived) {
      callbacks.onDone && callbacks.onDone({ request_id: requestId })
    }
  } catch (err) {
    // AbortError（主动取消）不触发错误回调，由 Chat.vue 的 abortLoading 处理
    if (err && err.name !== 'AbortError') {
      callbacks.onError && callbacks.onError(err)
    }
    throw err
  }

  return requestId
}
