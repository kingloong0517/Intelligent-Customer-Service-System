/**
 * 聊天 & AI 分类 API
 * - AI 分类：POST /ai-classify
 * - 聊天：POST /chat （SSE 流式，使用 fetch + ReadableStream）
 */
import request from '../utils/request'

/** AI 自动分类 */
export function aiClassify(userInput) {
  return request
    .post('/ai-classify', { user_input: userInput })
    .then((res) => res.data)
}

/**
 * 发送聊天消息 → SSE 流式响应
 * @param {object}   payload        {user_input, conversation_id, category}
 * @param {object}   callbacks      {onChar(char), onDone(), onError(err)}
 */
export function chatStream(payload, callbacks) {
  const token = localStorage.getItem('token')
  return fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify(payload),
  }).then(async (response) => {
    if (!response.ok) {
      const text = await response.text()
      callbacks && callbacks.onError && callbacks.onError(new Error(text || '发送消息失败'))
      throw new Error(text || '发送消息失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (!line.trim()) continue
        if (!line.startsWith('data: ')) continue
        const data = line.substring(6)
        if (data === '[DONE]') {
          callbacks && callbacks.onDone && callbacks.onDone()
          continue
        }
        callbacks && callbacks.onChar && callbacks.onChar(data)
      }
    }

    callbacks && callbacks.onDone && callbacks.onDone()
  })
}
