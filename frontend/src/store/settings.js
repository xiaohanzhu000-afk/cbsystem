/** 站点级配置（目前只有站点名称），登录页与主布局共用。 */
import { ref } from 'vue'
import api from '../api'

export const DEFAULT_SITE_NAME = 'CB后台管理系统'

export const siteName = ref(DEFAULT_SITE_NAME)

/** 页面标题 = 「当前页面 - 站点名称」 */
export function applyTitle(pageTitle) {
  const base = siteName.value || DEFAULT_SITE_NAME
  document.title = pageTitle ? `${pageTitle} - ${base}` : base
}

/**
 * 读取站点名称。
 * 对应接口是免鉴权的，因此登录页也能正常显示。
 * 如果配置不存在或读取失败，直接用代码里的默认值兜底。
 */
export async function loadSiteName() {
  try {
    const res = await api.get('/settings/public')
    const name = (res?.site_name || '').trim()
    siteName.value = name || DEFAULT_SITE_NAME
  } catch {
    siteName.value = DEFAULT_SITE_NAME
  }
  return siteName.value
}

export function setSiteName(name) {
  siteName.value = (name || '').trim() || DEFAULT_SITE_NAME
}
