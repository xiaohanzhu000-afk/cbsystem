<template>
  <div class="page">
    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="query.keyword"
          placeholder="搜索操作记录"
          clearable
          style="width: 240px"
          @keyup.enter="onSearch"
          @clear="onSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
        <el-button :icon="Refresh" @click="onReset">重置</el-button>

        <div class="spacer" />

        <el-button
          type="danger"
          :icon="Delete"
          :disabled="selectedIds.length === 0"
          :loading="removing"
          @click="onBatchDelete"
        >
          批量删除<template v-if="selectedIds.length">（{{ selectedIds.length }}）</template>
        </el-button>
        <el-button type="danger" plain :icon="DeleteFilled" :loading="clearing" @click="onClear">
          清空日志
        </el-button>
      </div>

      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="tableData"
        border
        stripe
        row-key="id"
        empty-text="暂无操作记录"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="46" reserve-selection />

        <el-table-column label="时间" width="215">
          <template #default="{ row }">
            <span class="log-time">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" min-width="360">
          <template #default="{ row }">
            <span :class="['log-action', actionClass(row.action)]">{{ row.action }}</span>
            <span v-if="row.target" class="log-target"> — {{ row.target }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onActivated, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, DeleteFilled, Refresh, Search } from '@element-plus/icons-vue'
import api from '../api'

const loading = ref(false)
const clearing = ref(false)
const removing = ref(false)
const tableRef = ref(null)
const tableData = ref([])
const total = ref(0)
/** 已勾选日志的 id；跨页保留，方便一次删掉多页的记录 */
const selectedIds = ref([])

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
})

/** 2026-09-16 16:35:09 → 2026年9月16日 16:35:09 */
function formatTime(value) {
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{2}:\d{2}:\d{2})/.exec(value || '')
  if (!m) return value || '-'
  return `${m[1]}年${Number(m[2])}月${Number(m[3])}日 ${m[4]}`
}

function actionClass(action) {
  const text = action || ''
  if (text.includes('删除') || text.includes('清空')) return 'act-danger'
  if (text.includes('新增')) return 'act-success'
  if (text.includes('修改')) return 'act-warning'
  if (text.includes('收藏')) return 'act-favorite'
  return 'act-plain'
}

function onSelectionChange(rows) {
  selectedIds.value = rows.map((row) => row.id)
}

function clearSelection() {
  selectedIds.value = []
  tableRef.value?.clearSelection()
}

/**
 * resetSelection：翻页时保持勾选，改动查询条件或删完之后则清空，
 * 否则很容易误删掉「上一批筛选结果」里勾中的记录。
 */
async function load(resetSelection = false) {
  loading.value = true
  try {
    const res = await api.get('/logs', {
      params: {
        page: query.page,
        page_size: query.page_size,
        keyword: query.keyword,
      },
    })
    if (resetSelection) clearSelection()
    tableData.value = res.items
    total.value = res.total
    if (tableData.value.length === 0 && query.page > 1) {
      query.page -= 1
      await load(resetSelection)
    }
  } finally {
    loading.value = false
  }
}

onActivated(() => load(true))

/** el-pagination 的 current-change 会把页码当参数传进来，用一层包装挡掉 */
function onPageChange() {
  load()
}

function onSearch() {
  query.page = 1
  load(true)
}

function onReset() {
  query.keyword = ''
  query.page = 1
  load(true)
}

function onSizeChange() {
  query.page = 1
  load(true)
}

async function onBatchDelete() {
  const count = selectedIds.value.length
  if (!count) return
  try {
    await ElMessageBox.confirm(
      `将删除选中的 ${count} 条日志，且无法恢复。确认继续吗？`,
      '批量删除',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  removing.value = true
  try {
    const res = await api.post('/logs/batch-delete', { ids: selectedIds.value })
    ElMessage.success(res.removed ? `已删除 ${res.removed} 条日志` : '选中的日志已不存在')
    await load(true)
  } finally {
    removing.value = false
  }
}

async function onClear() {
  try {
    await ElMessageBox.confirm('将删除全部操作日志，且无法恢复。确认继续吗？', '清空日志', {
      type: 'warning',
      confirmButtonText: '确认清空',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  clearing.value = true
  try {
    const res = await api.delete('/logs')
    ElMessage.success(res.removed ? `已清空 ${res.removed} 条日志` : '没有需要清空的日志')
    query.page = 1
    query.keyword = ''
    await load(true)
  } finally {
    clearing.value = false
  }
}
</script>

<style scoped>
.log-time {
  color: #606266;
  font-variant-numeric: tabular-nums;
}

.log-action {
  font-weight: 600;
}

.act-danger {
  color: #f56c6c;
}

.act-success {
  color: #67c23a;
}

.act-warning {
  color: #e6a23c;
}

.act-favorite {
  color: #409eff;
}

.act-plain {
  color: #303133;
}

.log-target {
  color: #303133;
}
</style>
