import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const api = axios.create({
  baseURL: '/api',
  timeout: 20000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cb_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error?.response?.status
    const detail = error?.response?.data?.detail

    if (status === 401) {
      localStorage.removeItem('cb_token')
      localStorage.removeItem('cb_username')
      if (router.currentRoute.value.name !== 'login') {
        ElMessage.error(detail || '登录已失效，请重新登录')
        router.replace('/login')
      }
    } else {
      const msg = typeof detail === 'string' ? detail : detail?.[0]?.msg || '请求失败'
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  }
)

/** 图片地址：本地代理或后端同源直接访问 */
export function fileUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//i.test(path) || path.startsWith('data:')) return path
  return path
}

export default api
