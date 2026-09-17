<template>
  <el-container class="layout">
    <el-aside width="216px" class="sidebar">
      <div class="brand">
        <div class="brand-logo">CB</div>
        <div class="brand-text">
          <div class="brand-title">{{ siteName }}</div>
          <div class="brand-sub">CB SYSTEM</div>
        </div>
      </div>

      <el-menu :default-active="activeMenu" router class="sidebar-menu">
        <el-menu-item index="/cb">
          <el-icon>
            <Document />
          </el-icon>
          <span>CB管理</span>
        </el-menu-item>
        <el-menu-item index="/favorites">
          <el-icon>
            <Star />
          </el-icon>
          <span>收藏记录</span>
        </el-menu-item>
        <el-menu-item index="/groups">
          <el-icon>
            <Files />
          </el-icon>
          <span>分组管理</span>
        </el-menu-item>
        <el-menu-item index="/sites">
          <el-icon>
            <Link />
          </el-icon>
          <span>网址管理</span>
        </el-menu-item>
        <el-menu-item index="/logs">
          <el-icon>
            <Tickets />
          </el-icon>
          <span>日志记录</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon>
            <Operation />
          </el-icon>
          <span>网站设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">{{ pageTitle }}</div>
        <div class="header-right">
          <el-dropdown @command="onCommand">
            <span class="user">
              <el-avatar :size="28" class="avatar">{{ avatarText }}</el-avatar>
              <span class="username">{{ username }}</span>
              <el-icon>
                <ArrowDown />
              </el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  ArrowDown,
  Document,
  Files,
  Link,
  Operation,
  Star,
  Tickets,
} from '@element-plus/icons-vue'
import { siteName } from '../store/settings'

const route = useRoute()
const router = useRouter()

const username = computed(() => localStorage.getItem('cb_username') || 'admin')
const avatarText = computed(() => (username.value || 'A').charAt(0).toUpperCase())
const activeMenu = computed(() => route.path)
const pageTitle = computed(() => route.meta.title || 'CB管理系统')

async function onCommand(command) {
  if (command !== 'logout') return
  try {
    await ElMessageBox.confirm('确认退出登录吗？', '提示', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  localStorage.removeItem('cb_token')
  localStorage.removeItem('cb_username')
  router.replace('/login')
}
</script>

<style scoped>
.layout {
  height: 100%;
}

.sidebar {
  background: #101a35;
  display: flex;
  flex-direction: column;
  color: #fff;
}

.brand {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-logo {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: linear-gradient(135deg, #2f6bff, #22d3ee);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}

.brand-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
}

.brand-sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}

.sidebar-menu {
  border-right: none;
  background: transparent;
  padding-top: 8px;
  flex: 1;
}

.sidebar-menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.72);
  height: 46px;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(47, 107, 255, 0.9), rgba(34, 211, 238, 0.55));
  color: #fff;
  border-radius: 0 22px 22px 0;
  margin-right: 12px;
}

.header {
  height: 64px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  position: relative;
  z-index: 10;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
}

.user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
  color: #1f2d3d;
}

.avatar {
  background: linear-gradient(135deg, #2f6bff, #22d3ee);
  font-size: 13px;
}

.username {
  font-size: 14px;
}

.main {
  background: #f5f7fa;
  padding: 20px;
}
</style>
