<template>
  <div class="page">
    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="query.keyword"
          :placeholder="searchPlaceholder"
          clearable
          style="width: 240px"
          @keyup.enter="onSearch"
          @clear="onSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <el-select
          v-model="query.group_id"
          placeholder="全部分组"
          clearable
          style="width: 170px"
          @change="onSearch"
        >
          <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>

        <el-select
          v-model="query.year"
          placeholder="全部年份"
          clearable
          style="width: 130px"
          @change="onSearch"
        >
          <el-option v-for="y in years" :key="y" :label="`${y} 年`" :value="y" />
        </el-select>

        <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
        <el-button :icon="Refresh" @click="onReset">重置</el-button>

        <div class="spacer" />

        <el-button type="primary" :icon="Plus" @click="onAdd">
          {{ isCbMode ? '新增 CB' : '新增收藏' }}
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="tableData"
        border
        stripe
        :row-key="rowKey"
        :empty-text="emptyText"
      >
        <el-table-column type="index" label="#" width="55" align="center" />

        <el-table-column label="CB名称" min-width="190">
          <template #default="{ row }">
            <el-input
              v-if="row._editing"
              v-model="row.name"
              maxlength="200"
              placeholder="请输入 CB 名称"
            />
            <span v-else class="cb-name">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column label="时间" width="155">
          <template #default="{ row }">
            <el-date-picker
              v-if="row._editing"
              v-model="row.event_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 100%"
            />
            <span v-else>{{ row.event_date || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="别名" min-width="190">
          <template #default="{ row }">
            <el-select
              v-if="row._editing"
              v-model="row.aliases"
              multiple
              filterable
              allow-create
              default-first-option
              :reserve-keyword="false"
              placeholder="输入后回车添加"
              style="width: 100%"
            />
            <div v-else-if="row.aliases && row.aliases.length" class="alias-list">
              <el-tag
                v-for="(alias, i) in row.aliases"
                :key="alias + i"
                type="info"
                effect="plain"
                size="small"
              >
                {{ alias }}
              </el-tag>
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="分组" width="170">
          <template #default="{ row }">
            <el-select
              v-if="row._editing"
              v-model="row.group_id"
              placeholder="请选择分组"
              clearable
              filterable
              style="width: 100%"
            >
              <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
            </el-select>
            <el-tag v-else-if="row.group_name" effect="light" round>{{ row.group_name }}</el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="图片" min-width="250">
          <template #default="{ row }">
            <!-- 查看模式：统一大小缩略图，点击放大预览 -->
            <div v-if="!row._editing" class="thumb-list">
              <el-image
                v-for="(img, i) in row.images"
                :key="img + i"
                class="thumb-item"
                :src="fileUrl(img)"
                fit="cover"
                :preview-src-list="row.images.map(fileUrl)"
                :initial-index="i"
                preview-teleported
                hide-on-click-modal
              />
              <span v-if="!row.images || row.images.length === 0" class="muted">-</span>
            </div>

            <!-- 编辑模式：可上传 / 可粘贴 / 可删除，最多 3 张 -->
            <div v-else>
              <div class="thumb-list">
                <div v-for="(img, i) in row.images" :key="img + i" class="thumb-item">
                  <el-image
                    :src="fileUrl(img)"
                    fit="cover"
                    :preview-src-list="row.images.map(fileUrl)"
                    :initial-index="i"
                    preview-teleported
                    hide-on-click-modal
                  />
                  <el-icon class="thumb-del" title="移除" @click.stop="removeImage(row, i)">
                    <Close />
                  </el-icon>
                </div>
                <div
                  v-if="row.images.length < MAX_IMAGES"
                  class="thumb-add"
                  title="点击上传图片"
                  @click="pickFile(row)"
                >
                  <el-icon><Plus /></el-icon>
                  <span>上传</span>
                </div>
              </div>
              <div class="paste-tip">
                最多 {{ MAX_IMAGES }} 张，可直接 Ctrl + V 粘贴图片（{{ row.images.length }}/{{ MAX_IMAGES }}）
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="备注" min-width="180">
          <template #default="{ row }">
            <el-input
              v-if="row._editing"
              v-model="row.remark"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              maxlength="500"
              placeholder="请输入备注"
            />
            <span v-else>{{ row.remark || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column
          label="操作"
          :width="isCbMode ? 250 : 170"
          align="center"
          fixed="right"
        >
          <template #default="{ row }">
            <template v-if="row._editing">
              <el-button type="primary" link :icon="Check" @click="onSave(row)">保存</el-button>
              <el-button link :icon="Close" @click="onCancel(row)">取消</el-button>
            </template>
            <template v-else>
              <el-button type="primary" link :icon="Edit" :disabled="!!editingRow" @click="onEdit(row)">
                编辑
              </el-button>

              <el-button
                v-if="isCbMode"
                link
                :type="row.is_favorite ? 'warning' : 'primary'"
                :icon="row.is_favorite ? StarFilled : Star"
                :disabled="!!editingRow"
                :loading="row._favoriting"
                @click="onToggleFavorite(row)"
              >
                {{ row.is_favorite ? '取消收藏' : '收藏' }}
              </el-button>

              <el-button type="danger" link :icon="Delete" :disabled="!!editingRow" @click="onDelete(row)">
                删除
              </el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="load"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>

    <input
      ref="fileInputRef"
      type="file"
      accept="image/*"
      multiple
      style="display: none"
      @change="onFileChange"
    />
  </div>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check,
  Close,
  Delete,
  Edit,
  Plus,
  Refresh,
  Search,
  Star,
  StarFilled,
} from '@element-plus/icons-vue'
import api, { fileUrl } from '../api'

const props = defineProps({
  /** cb：CB管理；favorite：收藏记录 */
  mode: { type: String, default: 'cb' },
})

const MAX_IMAGES = 3

const isCbMode = computed(() => props.mode === 'cb')
const basePath = computed(() => (isCbMode.value ? '/cb' : '/favorites'))
const emptyText = computed(() => (isCbMode.value ? '暂无 CB 数据' : '暂无收藏记录'))
const searchPlaceholder = computed(() =>
  isCbMode.value ? '搜索 CB 名称 / 别名' : '搜索名称 / 别名'
)

/** 今天的 YYYY-MM-DD，「时间」字段的默认值 */
function todayText() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const loading = ref(false)
const tableData = ref([])
const groups = ref([])
/** 数据里出现过的年份，倒序；由后端随列表一起返回 */
const years = ref([])
const total = ref(0)
const fileInputRef = ref(null)

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  group_id: null,
  year: null,
})

/** 当前处于编辑状态的行（同一时间只允许一行编辑） */
const editingRow = computed(() => tableData.value.find((r) => r._editing) || null)

const rowKey = (row) => row.id ?? row._key

function normalize(row) {
  return {
    ...row,
    images: Array.isArray(row.images) ? [...row.images] : [],
    aliases: Array.isArray(row.aliases) ? [...row.aliases] : [],
    group_id: row.group_id ?? null,
    remark: row.remark || '',
    event_date: row.event_date || '',
    is_favorite: !!row.is_favorite,
  }
}

async function load() {
  loading.value = true
  try {
    const res = await api.get(basePath.value, {
      params: {
        page: query.page,
        page_size: query.page_size,
        keyword: query.keyword,
        group_id: query.group_id || undefined,
        year: query.year || undefined,
      },
    })
    tableData.value = res.items.map(normalize)
    total.value = res.total
    years.value = res.years || []
    // 若当前页被删空，自动回退一页
    if (tableData.value.length === 0 && query.page > 1) {
      query.page -= 1
      await load()
    }
  } finally {
    loading.value = false
  }
}

async function loadGroups() {
  groups.value = await api.get('/groups')
}

/** 切换菜单回来时刷新数据；若正在编辑则保留编辑状态，避免丢失未保存的修改 */
onActivated(() => {
  window.addEventListener('paste', onPaste)
  loadGroups()
  if (!editingRow.value) load()
})

/** 离开页面时移除粘贴监听，避免影响另一个菜单 */
onDeactivated(() => {
  window.removeEventListener('paste', onPaste)
})

function onSearch() {
  if (editingRow.value) {
    ElMessage.warning('请先保存或取消正在编辑的数据')
    return
  }
  query.page = 1
  load()
}

function onReset() {
  if (editingRow.value) {
    ElMessage.warning('请先保存或取消正在编辑的数据')
    return
  }
  query.keyword = ''
  query.group_id = null
  query.year = null
  query.page = 1
  load()
}

function onSizeChange() {
  query.page = 1
  load()
}

function onAdd() {
  if (editingRow.value) {
    ElMessage.warning('请先保存或取消正在编辑的数据')
    return
  }
  if (query.page !== 1) {
    query.page = 1
  }
  tableData.value.unshift({
    _key: `new-${Date.now()}`,
    _isNew: true,
    _editing: true,
    id: null,
    name: '',
    group_id: null,
    group_name: '',
    remark: '',
    // 「时间」默认取今天，可以改成别的日期
    event_date: todayText(),
    aliases: [],
    images: [],
    is_favorite: false,
  })
}

function onEdit(row) {
  row._backup = {
    name: row.name,
    group_id: row.group_id,
    remark: row.remark,
    event_date: row.event_date,
    aliases: [...row.aliases],
    images: [...row.images],
  }
  row._editing = true
}

function onCancel(row) {
  if (row._isNew) {
    const index = tableData.value.indexOf(row)
    if (index > -1) tableData.value.splice(index, 1)
    return
  }
  if (row._backup) {
    row.name = row._backup.name
    row.group_id = row._backup.group_id
    row.remark = row._backup.remark
    row.event_date = row._backup.event_date
    row.aliases = [...row._backup.aliases]
    row.images = [...row._backup.images]
    delete row._backup
  }
  row._editing = false
}

async function onSave(row) {
  if (!row.name || !row.name.trim()) {
    ElMessage.warning('请输入 CB 名称')
    return
  }
  const payload = {
    name: row.name.trim(),
    group_id: row.group_id || null,
    remark: row.remark || '',
    event_date: row.event_date || '',
    aliases: (row.aliases || []).map((a) => String(a).trim()).filter(Boolean),
    images: row.images || [],
  }
  if (row._isNew) {
    await api.post(basePath.value, payload)
  } else {
    await api.put(`${basePath.value}/${row.id}`, payload)
  }
  ElMessage.success('保存成功')
  await load()
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await api.delete(`${basePath.value}/${row.id}`)
  ElMessage.success('删除成功')
  await load()
}

/** 收藏 / 取消收藏（仅 CB管理） */
async function onToggleFavorite(row) {
  row._favoriting = true
  try {
    const res = await api.post('/favorites/toggle', { cb_id: row.id })
    row.is_favorite = res.favorited
    ElMessage.success(res.favorited ? '已加入收藏记录' : '已取消收藏')
  } finally {
    row._favoriting = false
  }
}

/* ---------------- 图片处理 ---------------- */

/** 点击「上传」时记录目标行 */
let _currentRow = null

function findEditableRow() {
  return editingRow.value
}

function removeImage(row, index) {
  row.images.splice(index, 1)
}

function pickFile(row) {
  _currentRow = row
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
    fileInputRef.value.click()
  }
}

async function onFileChange(event) {
  const files = Array.from(event.target.files || [])
  const row = _currentRow || findEditableRow()
  if (row && files.length) {
    await uploadFiles(files, row)
  }
  _currentRow = null
}

async function uploadFiles(files, row) {
  const imageFiles = files.filter((f) => f.type && f.type.startsWith('image/'))
  if (!imageFiles.length) return

  let remain = MAX_IMAGES - row.images.length
  if (remain <= 0) {
    ElMessage.warning(`最多只能上传 ${MAX_IMAGES} 张图片`)
    return
  }
  if (imageFiles.length > remain) {
    ElMessage.warning(`最多只能上传 ${MAX_IMAGES} 张图片，已自动截取前 ${remain} 张`)
  }

  for (const file of imageFiles.slice(0, remain)) {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.post('/cb/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    if (res?.url) row.images.push(res.url)
    remain -= 1
  }
}

/** 支持直接把图片粘贴到表格里 */
async function onPaste(event) {
  const row = findEditableRow()
  if (!row) return

  const items = Array.from(event.clipboardData?.items || [])
  const imageFiles = items
    .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
    .map((item) => item.getAsFile())
    .filter(Boolean)

  if (imageFiles.length) {
    event.preventDefault()
    await uploadFiles(imageFiles, row)
    return
  }

  // 也支持粘贴图片地址文本
  const text = event.clipboardData?.getData('text') || ''
  const matched = text.trim().match(/^(https?:\/\/\S+|\/uploads\/\S+)$/i)
  if (matched) {
    event.preventDefault()
    if (row.images.length >= MAX_IMAGES) {
      ElMessage.warning(`最多只能上传 ${MAX_IMAGES} 张图片`)
      return
    }
    if (!row.images.includes(matched[0])) row.images.push(matched[0])
    ElMessage.success('已添加图片')
  }
}

onBeforeUnmount(() => {
  window.removeEventListener('paste', onPaste)
})
</script>

<style scoped>
.cb-name {
  font-weight: 500;
}

.alias-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

:deep(.el-table .cell) {
  vertical-align: middle;
}
</style>
