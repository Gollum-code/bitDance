import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: {
      // 回测引擎（trader 服务，真实 vn.py 回测）
      '/strategy': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 行情走 trader(8000) 的真实 TuShare 数据
      '/api/market': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 其余 API（auth / community / membership 等）走对象化后端
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
