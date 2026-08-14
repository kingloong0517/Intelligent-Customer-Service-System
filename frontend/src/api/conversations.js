/**
 * 会话 & 聊天记录 API
 */
import request from '../utils/request'

/** 会话列表 */
export function getConversations() {
  return request.get('/conversations').then((res) => res.data)
}

/** 创建会话 */
export function createConversation(title) {
  return request
    .post('/conversations', { title, status: 'active' })
    .then((res) => res.data)
}

/** 删除会话 */
export function deleteConversation(conversationId) {
  return request
    .delete(`/conversations/${conversationId}`)
    .then((res) => res.data)
}

/** 更新会话状态 */
export function updateConversationStatus(conversationId, status) {
  const token = localStorage.getItem('token')
  return fetch(`/api/conversations/${conversationId}/status`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify({ status }),
  })
}

/** 聊天记录（旧接口 /messages） */
export function getMessages(conversationId) {
  return request
    .get('/messages', { params: { conversation_id: conversationId } })
    .then((res) => res.data)
}

/** 聊天记录（新接口 /history） */
export function getHistory(conversationId, params = {}) {
  return request
    .get('/history', { params: { conversation_id: conversationId, ...params } })
    .then((res) => res.data)
}
