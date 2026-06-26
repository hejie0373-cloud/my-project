<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api/http'

const users = ref<any[]>([])
const loading = ref(false)

onMounted(() => loadUsers())

async function loadUsers() {
  loading.value = true
  const { data } = await http.get('/admin/users')
  users.value = (data as any).items || []
  loading.value = false
}

async function toggleUser(uid: string) {
  await http.put(`/admin/users/${uid}/toggle`)
  loadUsers()
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title" style="margin-bottom:24px">👥 用户管理</h1>
    <div class="card" style="padding:0;overflow:hidden">
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column prop="email" label="邮箱" min-width="160">
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column label="角色" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles" :key="r" size="small" style="margin-right:4px"
              :type="r === 'super_admin' ? 'danger' : r === 'store_owner' ? 'primary' : 'info'">
              {{ r === 'super_admin' ? '管理员' : r === 'store_owner' ? '店主' : r === 'staff' ? '店员' : r }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.isActive ? 'success' : 'danger'" size="small">{{ row.isActive ? '正常' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" :type="row.isActive ? 'danger' : 'success'" @click="toggleUser(row.id)">
              {{ row.isActive ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>
