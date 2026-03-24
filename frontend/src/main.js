import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import axios from 'axios'

// 检查本地存储中是否有 token
const token = localStorage.getItem('token')
if (token) {
  // 配置 axios 默认携带 token
  axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')