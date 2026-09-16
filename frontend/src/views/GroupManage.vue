<template>
  <div class="page">
    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索分组名称"
          clearable
          style="width: 220px"
          @input="onFilter"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div class="spacer" />
        <el-button type="primary" :icon="Plus" @click="onAdd">新增分组</el-button>
      </div>

      <el-table v-loading="loading" :data="filteredList" border stripe row-key="id" empty-text="暂无数据">
        <el-table-column type="index" label="#" width="55" align="center" />

        <el-table-column label="分组名称" min-width="220">
          <template #default="{ row }">
            <el-input
              v-if="row._editing"
              v-model="row.name"
              maxlength="50"
              placeholder="请输入分组名称"
            />
            <span v-else class="group-name">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column label="分组排序" width="220">
          <template #default="{ row }">
            <el-input-number
              v-if="row._editing"
              v-model="row.sort"
              :min="0"
              :max="9999"
              controls-position="right"
              style="width: 140px"
            />
            <span v-else>{{ row.sort }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="170" align="center">
          <template #default="{ row }">
            <template v-if="row._editing">
              <el-button type="primary" link :icon="Check" @click="onSave(row)">保存</el-button>
              <el-button link :icon="Close" @click="onCancel(row)">取消</el-button>
            </template>
            <template v-else>
              <el-button type="primary" link :icon="Edit" :disabled="!!editingRow" @click="onEdit(row)">
                编辑
              </el-button>
              <el-button type="danger" link :icon="Delete" :disabled="!!editingRow" @click="onDelete(row)">
                删除
              </el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Close, Delete, Edit, Plus, Search } from '@element-plus/icons-vue'
import api from '../api'

const loading = ref(false)
const list = ref([])
const keyword = ref('')

const editingRow = computed(() => list.value.find((r) => r._editing) || null)

const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return list.value
  return list.value.filter((g) => g.name.toLowerCase().includes(kw))
})

async function load() {
  loading.value = true
  try {
    const res = await api.get('/groups')
    list.value = res.map((g) => ({ ...g, sort: g.sort ?? 0 }))
  } finally {
    loading.value = false
  }
}

function onFilter() {
  /* 由 computed 自动过滤 */
}

function onAdd() {
  if (editingRow.value) {
    ElMessage.warning('请先保存或取消正在编辑的数据')
    return
  }
  const maxSort = list.value.reduce((max, g) => Math.max(max, Number(g.sort) || 0), 0)
  list.value.unshift({
    id: null,
    _isNew: true,
    _editing: true,
    name: '',
    sort: maxSort + 1,
  })
}

function onEdit(row) {
  row._backup = { name: row.name, sort: row.sort }
  row._editing = true
}

function onCancel(row) {
  if (row._isNew) {
    const index = list.value.indexOf(row)
    if (index > -1) list.value.splice(index, 1)
    return
  }
  if (row._backup) {
    row.name = row._backup.name
    row.sort = row._backup.sort
    delete row._backup
  }
  row._editing = false
}

async function onSave(row) {
  const name = (row.name || '').trim()
  if (!name) {
    ElMessage.warning('请输入分组名称')
    return
  }
  const payload = { name, sort: Number(row.sort) || 0 }
  if (row._isNew) {
    await api.post('/groups', payload)
  } else {
    await api.put(`/groups/${row.id}`, payload)
  }
  ElMessage.success('保存成功')
  await load()
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除分组「${row.name}」吗？该分组下的 CB 将变为未分组。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  await api.delete(`/groups/${row.id}`)
  ElMessage.success('删除成功')
  await load()
}

onMounted(load)
</script>

<style scoped>
.group-name {
  font-weight: 500;
}
</style>
