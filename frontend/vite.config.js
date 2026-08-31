import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  // P5.2：依赖拆分，把 Element Plus / highlight.js / marked 各自独立为 chunk，
  // 避免全部挤在 index.js 里；同时配合 Router 懒加载让 Chat/Knowledge 代码按需加载
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          'highlight': ['highlight.js'],
          'marked': ['marked'],
        }
      }
    }
  }
})