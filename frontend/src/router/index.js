import { createRouter, createWebHistory } from 'vue-router'
import { applyTitle } from '../store/settings'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/cb',
    children: [
      {
        path: 'cb',
        name: 'cb',
        component: () => import('../views/CbManage.vue'),
        meta: { title: 'CB管理', icon: 'Document' },
      },
      {
        path: 'favorites',
        name: 'favorites',
        component: () => import('../views/FavoriteManage.vue'),
        meta: { title: '收藏记录', icon: 'Star' },
      },
      {
        path: 'groups',
        name: 'groups',
        component: () => import('../views/GroupManage.vue'),
        meta: { title: '分组管理', icon: 'Files' },
      },
      {
        path: 'sites',
        name: 'sites',
        component: () => import('../views/SiteManage.vue'),
        meta: { title: '网址管理', icon: 'Link' },
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('../views/LogManage.vue'),
        meta: { title: '日志记录', icon: 'Tickets' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/SettingManage.vue'),
        meta: { title: '网站设置', icon: 'Setting' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('cb_token')
  if (!to.meta.public && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { path: '/' }
  }
  applyTitle(to.meta.title)
  return true
})

export default router
