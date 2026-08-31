<template>
  <div class="knowledge-container">
    <!-- 顶部栏 -->
    <header class="kb-header">
      <div class="kb-header-left">
        <h2>知识库管理</h2>
        <span class="kb-subtitle">企业客服知识库 · 为 RAG 检索提供数据支撑</span>
      </div>
      <div class="kb-header-right">
        <el-button @click="$router.push('/chat')">返回对话</el-button>
        <el-button type="danger" plain @click="handleLogout">退出登录</el-button>
      </div>
    </header>

    <div class="kb-main">
      <!-- 左侧：知识库列表 -->
      <aside class="kb-list-panel">
        <div class="panel-title">
          <span>知识库</span>
          <el-button type="primary" size="small" @click="showCreateDialog = true">新建</el-button>
        </div>
        <div v-if="kbList.length === 0 && !kbLoading" class="empty-tip">暂无知识库，请先新建</div>
        <div
          v-for="kb in kbList"
          :key="kb.id"
          class="kb-item"
          :class="{ active: currentKB && currentKB.id === kb.id }"
          @click="selectKB(kb.id)"
        >
          <div class="kb-item-name">{{ kb.name }}</div>
          <div class="kb-item-desc">{{ kb.description || '暂无描述' }}</div>
          <div class="kb-item-meta">
            文档 {{ kb.document_count }} 个 · 已就绪 {{ kb.ready_count }} 个
            <el-icon class="kb-delete" @click.stop="handleDeleteKB(kb)"><Delete /></el-icon>
          </div>
        </div>
      </aside>

      <!-- 右侧：文档管理 -->
      <section class="kb-doc-panel">
        <template v-if="currentKB">
          <div class="panel-title">
            <span>{{ currentKB.name }} · 文档列表</span>
            <el-upload
              :show-file-list="false"
              accept=".pdf,.txt,.md"
              :http-request="handleUpload"
            >
              <el-button type="primary" size="small" :loading="uploading">上传文档</el-button>
            </el-upload>
          </div>
          <div class="upload-tip">支持 PDF / TXT / Markdown，最大 10MB</div>

          <el-table :data="documents" v-loading="docLoading" style="width: 100%">
            <el-table-column prop="filename" label="文件名" min-width="180" show-overflow-tooltip />
            <el-table-column prop="file_type" label="类型" width="70" align="center" />
            <el-table-column label="大小" width="90" align="center">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110" align="center">
              <template #default="{ row }">
                <el-tooltip :disabled="!row.error_message" :content="row.error_message" placement="top">
                  <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="chunk_count" label="分块数" width="80" align="center" />
            <el-table-column prop="embedding_model" label="Embedding" width="130" show-overflow-tooltip />
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="showChunks(row)">分块</el-button>
                <el-button link type="danger" size="small" @click="handleDeleteDoc(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <div v-else class="empty-tip large">请选择或创建知识库</div>
      </section>
    </div>

    <!-- 新建知识库对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建知识库" width="420px">
      <el-form label-width="70px">
        <el-form-item label="名称" required>
          <el-input v-model="newKB.name" placeholder="如：产品手册知识库" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newKB.description" type="textarea" :rows="3" placeholder="知识库用途说明（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreateKB">创建</el-button>
      </template>
    </el-dialog>

    <!-- 分块查看抽屉 -->
    <el-drawer v-model="chunksDrawer" :title="`分块预览：${chunkDocName}`" size="40%">
      <div v-if="chunks.length === 0" class="empty-tip">该文档暂无分块</div>
      <div v-for="chunk in chunks" :key="chunk.id" class="chunk-card">
        <div class="chunk-head">#{{ chunk.chunk_index }} · {{ chunk.char_count }} 字符</div>
        <div class="chunk-content">{{ chunk.content }}</div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import {
  createKB,
  listKBs,
  getKBDetail,
  deleteKB,
  uploadDocument,
  deleteDocument,
  listChunks,
} from '../api/kb'

const router = useRouter()

// ---------- 状态 ----------
const kbList = ref([])
const currentKB = ref(null)
const documents = ref([])
const kbLoading = ref(false)
const docLoading = ref(false)
const uploading = ref(false)
const creating = ref(false)
const showCreateDialog = ref(false)
const newKB = ref({ name: '', description: '' })
const chunksDrawer = ref(false)
const chunkDocName = ref('')
const chunks = ref([])

let pollTimer = null

// ---------- 工具 ----------
const statusText = (s) => ({ pending: '等待处理', processing: '处理中', ready: '已就绪', failed: '失败' }[s] || s)
const statusTagType = (s) => ({ pending: 'info', processing: 'warning', ready: 'success', failed: 'danger' }[s] || 'info')
const formatSize = (bytes) => {
  if (bytes == null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

// ---------- 数据加载 ----------
const loadKBList = async () => {
  kbLoading.value = true
  try {
    kbList.value = await listKBs()
    if (currentKB.value) {
      const still = kbList.value.find((k) => k.id === currentKB.value.id)
      if (!still) {
        currentKB.value = null
        documents.value = []
      }
    }
  } catch (err) {
    console.error('加载知识库列表失败:', err)
  } finally {
    kbLoading.value = false
  }
}

const selectKB = async (kbId) => {
  docLoading.value = true
  try {
    const detail = await getKBDetail(kbId)
    currentKB.value = detail
    documents.value = detail.documents || []
    schedulePoll()
  } catch (err) {
    ElMessage.error('加载知识库详情失败')
  } finally {
    docLoading.value = false
  }
}

// 文档存在 pending/processing 时轮询刷新处理状态
const schedulePoll = () => {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  const processing = documents.value.some((d) => d.status === 'pending' || d.status === 'processing')
  if (processing && currentKB.value) {
    pollTimer = setTimeout(async () => {
      try {
        const detail = await getKBDetail(currentKB.value.id)
        documents.value = detail.documents || []
      } catch { /* 轮询失败忽略，下轮重试 */ }
      schedulePoll()
    }, 2000)
  }
}

// ---------- 操作 ----------
const handleCreateKB = async () => {
  if (!newKB.value.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  creating.value = true
  try {
    const kb = await createKB({ name: newKB.value.name.trim(), description: newKB.value.description.trim() || null })
    ElMessage.success('知识库创建成功')
    showCreateDialog.value = false
    newKB.value = { name: '', description: '' }
    await loadKBList()
    selectKB(kb.id)
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

const handleDeleteKB = async (kb) => {
  try {
    await ElMessageBox.confirm(
      `确定删除知识库「${kb.name}」？其下所有文档、分块与向量数据将一并删除。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteKB(kb.id)
    ElMessage.success('知识库已删除')
    if (currentKB.value?.id === kb.id) {
      currentKB.value = null
      documents.value = []
    }
    loadKBList()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '删除失败')
  }
}

const handleUpload = async (options) => {
  if (!currentKB.value) {
    ElMessage.warning('请先选择知识库')
    return
  }
  uploading.value = true
  try {
    const doc = await uploadDocument(currentKB.value.id, options.file)
    ElMessage.success(`文档「${doc.filename}」已上传，正在后台处理`)
    await selectKB(currentKB.value.id)
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

const handleDeleteDoc = async (doc) => {
  try {
    await ElMessageBox.confirm(`确定删除文档「${doc.filename}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteDocument(currentKB.value.id, doc.id)
    ElMessage.success('文档已删除')
    selectKB(currentKB.value.id)
    loadKBList()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '删除失败')
  }
}

const showChunks = async (doc) => {
  try {
    chunks.value = await listChunks(currentKB.value.id, doc.id)
    chunkDocName.value = doc.filename
    chunksDrawer.value = true
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '加载分块失败')
  }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}

onMounted(loadKBList)
onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<style scoped>
.knowledge-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}

.kb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.kb-header-left h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.kb-subtitle {
  font-size: 12px;
  color: #909399;
}

.kb-main {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 16px 24px;
  overflow: hidden;
}

.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

/* 左侧列表 */
.kb-list-panel {
  width: 280px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  padding: 16px;
  overflow-y: auto;
}

.kb-item {
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.kb-item:hover {
  border-color: #409eff;
}

.kb-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.kb-item-name {
  font-weight: 600;
  color: #303133;
}

.kb-item-desc {
  font-size: 12px;
  color: #909399;
  margin: 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-item-meta {
  font-size: 12px;
  color: #67c23a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kb-delete {
  color: #f56c6c;
  cursor: pointer;
}

/* 右侧文档 */
.kb-doc-panel {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  padding: 16px;
  overflow-y: auto;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-bottom: 12px;
}

.empty-tip {
  color: #909399;
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}

.empty-tip.large {
  padding-top: 120px;
  font-size: 15px;
}

/* 分块预览 */
.chunk-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 10px;
}

.chunk-head {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.chunk-content {
  font-size: 13px;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}
</style>
