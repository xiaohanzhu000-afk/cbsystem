<template>
  <div class="page">
    <el-card v-loading="loading" shadow="never" class="setting-card">
      <el-form :model="form" label-width="120px">
        <el-form-item label="站点名称">
          <el-input
            v-model="form.site_name"
            maxlength="50"
            show-word-limit
            placeholder="请输入站点名称"
          />
          <div class="tip">显示在浏览器标签、登录页标题和侧边栏顶部。</div>
        </el-form-item>

        <el-form-item label="图片存放位置">
          <div class="dir-row">
            <el-input v-model="form.image_dir" placeholder="例如 D:\cbsystem\images" />
            <el-button :icon="FolderOpened" :loading="picking" @click="onPickFolder">
              浏览...
            </el-button>
          </div>
          <div class="tip">
            当前目录：<code>{{ current.image_dir }}</code>，共 {{ current.image_count }} 张图片。
            <br />
            留空则恢复为默认目录 <code>{{ current.default_image_dir }}</code>。
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="onSave">保存设置</el-button>
          <el-button :disabled="loading" @click="onRestoreDefault">恢复默认目录</el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <div class="section">
        <div class="section-title">图片清理</div>
        <div class="tip">
          某个 CB 在「CB管理」和「收藏记录」里<b>都</b>被删除后，它的图片会自动从磁盘移除；
          这里可以额外清理掉那些上传后未保存、已经没有任何记录引用的图片。
        </div>
        <el-button
          class="section-btn"
          type="warning"
          plain
          :icon="Delete"
          :loading="cleaning"
          @click="onCleanup"
        >
          清理未引用图片
        </el-button>
      </div>

      <el-divider />

      <div class="section">
        <div class="section-title">数据备份</div>
        <div class="tip">
          导出的数据包是一个 <code>.zip</code> 文件，内含<b>分组、CB管理、收藏记录、网址管理</b>
          及其用到的<b>图片</b>，可在任意一台机器上恢复。
          <br />
          数据包<b>不含</b>管理员账号密码，恢复后仍使用当前账号登录。
        </div>
        <div class="backup-actions">
          <el-button
            type="primary"
            plain
            :icon="Download"
            :loading="backingUp"
            @click="onBackup"
          >
            备份数据
          </el-button>
          <el-button
            type="danger"
            plain
            :icon="Upload"
            :loading="restoring"
            @click="pickFile"
          >
            恢复备份
          </el-button>
          <input
            ref="fileInput"
            class="file-input"
            type="file"
            accept=".zip,application/zip"
            @change="onFilePicked"
          />
        </div>
        <div class="tip warn">
          恢复会用数据包<b>覆盖</b>当前全部分组、CB、收藏记录、网址和图片，请先备份再操作。
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onActivated, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, FolderOpened, Upload } from '@element-plus/icons-vue'
import api from '../api'
import { applyTitle, setSiteName } from '../store/settings'

const loading = ref(false)
const saving = ref(false)
const picking = ref(false)
const cleaning = ref(false)
const backingUp = ref(false)
const restoring = ref(false)
const fileInput = ref(null)

const current = reactive({
  site_name: '',
  image_dir: '',
  default_image_dir: '',
  image_count: 0,
})

const form = reactive({ site_name: '', image_dir: '' })

function apply(data) {
  Object.assign(current, data)
  form.site_name = data.site_name
  form.image_dir = data.image_dir
}

async function load() {
  loading.value = true
  try {
    apply(await api.get('/settings'))
  } finally {
    loading.value = false
  }
}

onActivated(load)

async function onPickFolder() {
  picking.value = true
  try {
    const res = await api.post('/settings/pick-folder')
    if (res?.cancelled) return
    if (res?.path) {
      form.image_dir = res.path
      ElMessage.success('已选择文件夹')
    }
  } catch {
    /* 环境不支持时会给出提示，用户可手动填写路径 */
  } finally {
    picking.value = false
  }
}

function onRestoreDefault() {
  form.image_dir = current.default_image_dir
  ElMessage.info('已填回默认目录，点击「保存设置」生效')
}

async function onSave() {
  if (!form.site_name.trim()) {
    ElMessage.warning('请输入站点名称')
    return
  }

  const dirChanged = form.image_dir.trim() !== current.image_dir
  if (dirChanged) {
    try {
      await ElMessageBox.confirm(
        `图片目录将切换到「${form.image_dir.trim() || current.default_image_dir}」，` +
          `当前 ${current.image_count} 张图片会自动移动到新目录，确认继续吗？`,
        '更换图片目录',
        { type: 'warning', confirmButtonText: '确认更换', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }

  saving.value = true
  try {
    const res = await api.put('/settings', {
      site_name: form.site_name.trim(),
      image_dir: form.image_dir.trim(),
    })
    apply(res)
    setSiteName(res.site_name)
    applyTitle('网站设置')

    let msg = '保存成功'
    if (dirChanged && res.moved) msg += `，已移动 ${res.moved} 张图片`
    if (res.failed?.length) msg += `，${res.failed.length} 张图片移动失败`
    ElMessage.success(msg)
  } finally {
    saving.value = false
  }
}

async function onCleanup() {
  try {
    await ElMessageBox.confirm(
      '将删除磁盘上已不被任何 CB / 收藏记录引用的图片，确认继续吗？',
      '清理未引用图片',
      { type: 'warning', confirmButtonText: '开始清理', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  cleaning.value = true
  try {
    const res = await api.post('/settings/cleanup-images')
    ElMessage.success(
      res.removed ? `已清理 ${res.removed} 张未引用图片` : '没有需要清理的图片'
    )
    current.image_count = res.remaining
  } finally {
    cleaning.value = false
  }
}

/** cbsystem-backup-20260916-103000.zip */
function backupFileName() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return (
    'cbsystem-backup-' +
    `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
    `-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}.zip`
  )
}

async function onBackup() {
  backingUp.value = true
  try {
    // 数据量大时导出较慢，单独放宽超时时间
    const blob = await api.get('/settings/backup', {
      responseType: 'blob',
      timeout: 120000,
    })
    const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    link.download = backupFileName()
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('备份数据包已导出')
  } finally {
    backingUp.value = false
  }
}

function pickFile() {
  fileInput.value?.click()
}

async function onFilePicked(event) {
  const file = event.target.files?.[0]
  event.target.value = '' // 清空后可以连续选择同一个文件
  if (!file) return

  try {
    await ElMessageBox.confirm(
      `将用「${file.name}」覆盖当前全部分组、CB、收藏记录、网址和图片，且无法撤销。确认继续吗？`,
      '恢复备份',
      { type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  restoring.value = true
  try {
    const data = new FormData()
    data.append('file', file)
    const res = await api.post('/settings/restore', data, { timeout: 120000 })

    await load()
    setSiteName(res.site_name)
    applyTitle('网站设置')

    let msg =
      `恢复完成：分组 ${res.groups} 个、CB ${res.cb} 条、` +
      `收藏 ${res.favorites} 条、网址 ${res.sites ?? 0} 条、图片 ${res.images} 张`
    if (res.removed) msg += `，已清理 ${res.removed} 张无效图片`
    ElMessage.success(msg)
  } finally {
    restoring.value = false
  }
}
</script>

<style scoped>
.setting-card {
  max-width: 780px;
}

.dir-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

.tip {
  font-size: 12px;
  line-height: 1.7;
  color: #909399;
}

.tip code {
  background: #f5f7fa;
  padding: 1px 5px;
  border-radius: 4px;
  color: #475669;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
  margin-bottom: 8px;
}

.section-btn {
  margin-top: 12px;
}

.backup-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}

.file-input {
  display: none;
}

.warn {
  margin-top: 10px;
  color: #e6a23c;
}
</style>
