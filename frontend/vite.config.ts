import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    // 开发环境把 /api 代理到后端，避免跨域
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
    // WSL 下 /mnt/d 挂载不支持 inotify，必须轮询监听否则 HMR 失效
    watch: { usePolling: true, interval: 1000 },
  },
  // 生产预览（npm run preview）：同样代理 /api，打包产物直接可跑
  preview: {
    port: 4173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
