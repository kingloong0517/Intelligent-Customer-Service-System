/**
 * 认证 API：登录、注册、登出（同步 token 工具一并 re-export 供 Login.vue 使用）
 */
import request from '../utils/request'
// re-export：Login.vue 从本模块 import syncGlobalAuthorization 保持与原 import 路径一致
export { syncGlobalAuthorization } from '../utils/request'
import { syncGlobalAuthorization } from '../utils/request'

/**
 * 登录
 * 后端 /login 接收 form-urlencoded（OAuth2 标准）
 */
export function login(username, password) {
  const params = new URLSearchParams()
  params.append('username', username)
  params.append('password', password)
  return request
    .post('/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    .then((res) => res.data)
}

/** 注册 */
export function register(username, password) {
  return request
    .post('/register', { username, password })
    .then((res) => res.data)
}

/** 登出（纯前端：清除 token + 同步全局 axios） */
export function logout() {
  localStorage.removeItem('token')
  syncGlobalAuthorization()
}
