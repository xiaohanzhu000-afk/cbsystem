<template>
  <div class="page">
    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="query.keyword"
          placeholder="搜索网址 / 测试内链 / 备注"
          clearable
          style="width: 240px"
          @keyup.enter="onSearch"
          @clear="onSearch"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <el-select v-model="query.status" style="width: 130px" @change="onSearch">
          <el-option label="全部状态" value="" />
          <el-option label="正常" value="正常" />
          <el-option label="作废" value="作废" />
        </el-select>

        <el-button type="primary" :icon="Search" @click="onSearch">查询</el-button>
        <el-button :icon="Refresh" @click="onReset">重置</el-button>

        <div class="spacer" />

        <el-button type="primary" :icon="Plus" :disabled="!!editingRow" @click="onAdd">
          新增网址
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="tableData"
        border
        stripe
        empty-text="暂无网址数据"
      >
        <el-table-column type="index" label="#" width="55" align="center" />

        <el-table-column label="网址" min-width="230" show-overflow-tooltip>
          <template #default="{ row }">
            <el-input
              v-if="row._editing"
              v-model="row.url"
              placeholder="例如 example.com 或 https://example.com"
            />
            <a
              v-else-if="row.url"
              class="link"
              :href="row.url"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ row.url }}
            </a>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="创建日期" width="160">
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

        <el-table-column label="测试内链" min-width="210" show-overflow-tooltip>
          <template #default="{ row }">
            <el-input
              v-if="row._editing"
              v-model="row.test_url"
              placeholder="选填，例如 https://test.example.com"
            />
            <a
              v-else-if="row.test_url"
              class="link"
              :href="row.test_url"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ row.test_url }}
            </a>
            <span v-else class="muted">-</span>
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

        <el-table-column label="作用级别" width="120" align="center">
          <template #default="{ row }">
            <el-select
              v-if="row._editing"
              v-model="row.level"
              style="width: 88px"
            >
              <el-option v-for="n in LEVELS" :key="n" :label="`${n} 级`" :value="n" />
            </el-select>
            <el-tag v-else size="small" effect="plain">{{ row.level }} 级</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="提供下载" width="110" align="center">
          <template #default="{ row }">
            <el-select v-if="row._editing" v-model="row.downloadable" style="width: 80px">
              <el-option label="是" :value="true" />
              <el-option label="否" :value="false" />
            </el-select>
            <el-tag v-else size="small" :type="row.downloadable ? 'success' : 'info'" effect="plain">
              {{ row.downloadable ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="95" align="center">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === '作废' ? 'danger' : 'success'"
              effect="plain"
            >
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="215" align="center" fixed="right">
          <template #default="{ row }">
            <template v-if="row._editing">
              <el-button type="primary" link :icon="Check" @click="onSave(row)">保存</el-button>
              <el-button link :icon="Close" @click="onCancel(row)">取消</el-button>
            </template>
            <template v-else>
              <el-button
                type="primary"
                link
                :icon="Edit"
                :disabled="!!editingRow"
                @click="onEdit(row)"
              >
                编辑
              </el-button>
              <el-button
                :type="row.status === '作废' ? 'success' : 'warning'"
                link
                :icon="row.status === '作废' ? RefreshLeft : CircleClose"
                :disabled="!!editingRow"
                @click="onToggleStatus(row)"
              >
                {{ row.status === '作废' ? '恢复' : '作废' }}
              </el-button>
              <el-button
                type="danger"
                link
                :icon="Delete"
                :disabled="!!editingRow"
                @click="onDelete(row)"
              >
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
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onActivated, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check,
  CircleClose,
  Close,
  Delete,
  Edit,
  Plus,
  Refresh,
  RefreshLeft,
  Search,
} from '@element-plus/icons-vue'
import api from '../api'

const LEVELS = [1, 2, 3, 4, 5]

const loading = ref(false)
const tableData = ref([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  status: '',
})

/** 同一时间只允许编辑一行，避免两个保存请求互相覆盖 */
const editingRow = computed(() => tableData.value.find((r) => r._editing) || null)

/** 今天的 YYYY-MM-DD，「创建日期」的默认值 */
function todayText() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function normalize(row) {
  return {
    ...row,
    url: row.url || '',
    test_url: row.test_url || '',
    event_date: row.event_date || '',
    level: Number(row.level) || 1,
    downloadable: !!row.downloadable,
    status: row.status || '正常',
    remark: row.remark || '',
  }
}

async function load() {
  loading.value = true
  try {
    const res = await api.get('/sites', {
      params: {
        page: query.page,
        page_size: query.page_size,
        keyword: query.keyword,
        status: query.status,
      },
    })
    tableData.value = res.items.map(normalize)
    total.value = res.total
    if (tableData.value.length === 0 && query.page > 1) {
      query.page -= 1
      await load()
    }
  } finally {
    loading.value = false
  }
}

onActivated(load)

function onPageChange() {
  load()
}

function onSearch() {
  query.page = 1
  load()
}

function onReset() {
  query.keyword = ''
  query.status = ''
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
  tableData.value.unshift({
    _isNew: true,
    _editing: true,
    id: null,
    url: '',
    event_date: todayText(),
    test_url: '',
    level: 1,
    downloadable: false,
    status: '正常',
    remark: '',
  })
}

function onEdit(row) {
  row._backup = {
    url: row.url,
    event_date: row.event_date,
    test_url: row.test_url,
    level: row.level,
    downloadable: row.downloadable,
    remark: row.remark,
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
    Object.assign(row, row._backup)
    delete row._backup
  }
  row._editing = false
}

async function onSave(row) {
  if (!(row.url || '').trim()) {
    ElMessage.warning('请输入网址')
    return
  }
  const payload = {
    url: row.url.trim(),
    event_date: row.event_date || '',
    test_url: (row.test_url || '').trim(),
    level: Number(row.level) || 1,
    downloadable: !!row.downloadable,
    status: row.status || '正常',
    remark: row.remark || '',
  }
  if (row._isNew) {
    await api.post('/sites', payload)
  } else {
    await api.put(`/sites/${row.id}`, payload)
  }
  ElMessage.success('保存成功')
  await load()
}

async function onToggleStatus(row) {
  const toVoid = row.status !== '作废'
  if (toVoid) {
    try {
      await ElMessageBox.confirm(
        `确认作废「${row.url}」吗？作废后可以随时恢复。`,
        '作废确认',
        { type: 'warning', confirmButtonText: '作废', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }
  const res = await api.post(`/sites/${row.id}/toggle-status`)
  ElMessage.success(res.status === '作废' ? '已作废' : '已恢复')
  await load()
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除「${row.url}」吗？删除后不可恢复，如果只是想停用，建议改用「作废」。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  await api.delete(`/sites/${row.id}`)
  ElMessage.success('删除成功')
  await load()
}
</script>

<style scoped>
.link {
  color: #409eff;
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}
</style>
