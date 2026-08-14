/**
 * axios 统一封装：基础地址、token 注入、401 自动退出
 * （views 不再直连全局 axios，统一走 request 实例）
 */
import axios from 'axios'
import router from '../router'

const request = axios.create({
  // vite 代理：/api -> http://localhost:8000，无需写绝对地址
  baseURL: '/api',
  timeout: 30000,
})

// ===== 请求拦截器：注入 token =====
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ===== 响应拦截器：401 自动登出 =====
request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      // 避免循环跳转
      if (router.currentRoute.value.name !== 'Login') {
        router.push({ name: 'Login' })
      }
    }
    return Promise.reject(error)
  }
)

/** 同步全局 axios 的 Authorization，兼容 Chat.vue 中仍在使用全局 axios 的场景 */
export function syncGlobalAuthorization() {
  const token = localStorage.getItem('token')
  if (token) {
    axios.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    delete axios.defaults.headers.common.Authorization
  }
}

// 初始化一次
syncGlobalAuthorization()

export default request
