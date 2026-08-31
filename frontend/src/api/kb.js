/**
 * 知识库 API（P2.1）
 * 走统一 request 封装（自动带 token、401 拦截）
 */
import request from '../utils/request'

/** 创建知识库 */
export function createKB(data) {
  return request.post('/kb', data).then((res) => res.data)
}

/** 知识库列表（含文档统计） */
export function listKBs() {
  return request.get('/kb').then((res) => res.data)
}

/** 知识库详情（含文档列表） */
export function getKBDetail(kbId) {
  return request.get(`/kb/${kbId}`).then((res) => res.data)
}

/** 删除知识库（级联删除文档与向量） */
export function deleteKB(kbId) {
  return request.delete(`/kb/${kbId}`).then((res) => res.data)
}

/** 上传文档（multipart） */
export function uploadDocument(kbId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return request
    .post(`/kb/${kbId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((res) => res.data)
}

/** 删除文档（级联删除分块与向量） */
export function deleteDocument(kbId, docId) {
  return request.delete(`/kb/${kbId}/documents/${docId}`).then((res) => res.data)
}

/** 查看文档分块 */
export function listChunks(kbId, docId) {
  return request.get(`/kb/${kbId}/documents/${docId}/chunks`).then((res) => res.data)
}

/** 检索调试 */
export function searchKB(kbId, query, topK = 5) {
  return request.post(`/kb/${kbId}/search`, { query, top_k: topK }).then((res) => res.data)
}
