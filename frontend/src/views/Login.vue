<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <div class="logo">CB</div>
        <h1>{{ siteName }}</h1>
        <p>CB SYSTEM Management System</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" @submit.prevent="onSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="请输入账号" clearable>
            <template #prefix><el-icon>
                <User />
              </el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password @keyup.enter="onSubmit">
            <template #prefix><el-icon>
                <Lock />
              </el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="login-btn" :loading="loading" @click="onSubmit">
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-tip">默认账号：admin / admin123</div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { siteName } from '../store/settings'

const router = useRouter()
const route = useRoute()

const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: 'admin', password: '' })

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await api.post('/auth/login', {
        username: form.username.trim(),
        password: form.password,
      })
      localStorage.setItem('cb_token', res.token)
      localStorage.setItem('cb_username', res.username)
      ElMessage.success('登录成功')
      router.replace(route.query.redirect || '/')
    } catch (e) {
      /* 错误提示已由拦截器统一处理 */
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f4bd8 0%, #4f8cff 45%, #22d3ee 100%);
  padding: 24px;
}

.login-card {
  width: 400px;
  padding: 40px 36px 28px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(15, 35, 95, 0.28);
}

.login-brand {
  text-align: center;
  margin-bottom: 28px;
}

.logo {
  width: 60px;
  height: 60px;
  margin: 0 auto 14px;
  border-radius: 16px;
  background: linear-gradient(135deg, #1f4bd8, #22d3ee);
  color: #fff;
  font-weight: 700;
  font-size: 22px;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-brand h1 {
  font-size: 20px;
  margin: 0 0 6px;
  color: #1f2d3d;
}

.login-brand p {
  margin: 0;
  font-size: 12px;
  color: #909399;
  letter-spacing: 0.5px;
}

.login-btn {
  width: 100%;
  letter-spacing: 4px;
}

.login-tip {
  text-align: center;
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
