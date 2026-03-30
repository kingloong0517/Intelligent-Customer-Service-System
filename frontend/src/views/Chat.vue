<template>
  <div class="chat-container">
    <!-- 左侧会话列表 -->
    <div class="sidebar">
      <div class="sidebar-header">
        <h3>会话</h3>
        <el-button type="primary" size="small" @click="showCreateDialog = true">新建会话</el-button>
      </div>
      <div class="conversation-list">
        <div 
          v-for="conversation in conversations" 
          :key="conversation.id"
          class="conversation-item"
          :class="{ active: currentConversationId === conversation.id }"
          @click="switchConversation(conversation.id)"
        >
          <div class="conversation-main">
            <div class="conversation-title-container">
              <div class="conversation-title">{{ conversation.title }}</div>
              <el-tag 
                :type="getStatusTagType(conversation.status)" 
                size="small"
                class="conversation-status"
              >
                {{ getStatusText(conversation.status) }}
              </el-tag>
            </div>
            <div v-if="conversation.last_message" class="conversation-last-message">{{ conversation.last_message }}</div>
            <div class="conversation-footer">
              <div class="conversation-time">{{ formatTime(conversation.updated_at) }}</div>
              <span class="message-count">{{ conversation.message_count }} 条</span>
            </div>
          </div>
          <el-button 
            type="danger" 
            size="mini" 
            @click.stop="deleteConversation(conversation.id)"
            circle
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
    
    <!-- 右侧聊天区域 -->
    <div class="chat-area">
      <div class="chat-header">
        <div class="chat-header-left">
          <h2>{{ currentConversation?.title || 'AI 聊天' }}</h2>
          <el-tag 
            v-if="currentConversation?.status" 
            :type="getStatusTagType(currentConversation.status)" 
            size="small"
            class="header-status-tag"
          >
            {{ getStatusText(currentConversation.status) }}
          </el-tag>
          <span v-if="currentConversation?.message_count" class="message-count">
            {{ currentConversation.message_count }} 条消息
          </span>
        </div>
        <div class="chat-header-right">
          <el-select 
            v-model="currentConversationStatus" 
            placeholder="修改状态" 
            size="small"
            @change="updateConversationStatus"
          >
            <el-option label="进行中" value="active"></el-option>
            <el-option label="已结束" value="ended"></el-option>
            <el-option label="已归档" value="archived"></el-option>
          </el-select>
          <el-button type="warning" @click="handleLogout">退出登录</el-button>
        </div>
      </div>
      
      <div v-if="currentConversationId" class="chat-messages">
        <!-- 用户消息项 -->
        <div 
          v-for="msg in chatMessages" 
          :key="msg.id"
          class="message-item"
        >
          <!-- 显示用户消息（如果存在） -->
          <div v-if="msg.message" class="message-bubble user-message">
            <div class="message-header">
              <strong class="message-author">我</strong>
              <el-tag v-if="msg.category" type="success" size="small" class="message-category">
                {{ msg.category }}
              </el-tag>
            </div>
            <div class="message-content" v-html="renderMarkdown(msg.message)"></div>
          </div>
          
          <!-- 显示AI回复（如果存在） -->
          <div v-if="msg.response" class="message-bubble ai-message">
            <div class="message-header">
              <strong class="message-author">AI</strong>
            </div>
            <div class="message-content" v-html="renderMarkdown(msg.response)"></div>
          </div>
        </div>
      </div>
      
      <div v-else class="chat-empty">
        <el-empty description="请选择或创建一个会话开始聊天"></el-empty>
      </div>
      
      <div class="chat-input" v-if="currentConversationId">
        <!-- 客服问题分类选择器 -->
        <div class="category-selector">
          <el-select v-model="selectedCategory" placeholder="请选择问题分类" size="small" style="width: 200px; margin-bottom: 12px;">
            <el-option
              v-for="category in categories"
              :key="category.id"
              :label="category.name"
              :value="category.name"
            >
              <div>
                <span>{{ category.name }}</span>
                <span class="category-desc">{{ category.description }}</span>
              </div>
            </el-option>
          </el-select>
          <el-tag 
            v-for="category in recentCategories" 
            :key="category" 
            type="info" 
            size="small" 
            @click="selectedCategory = category"
            class="recent-category"
          >
            {{ category }}
          </el-tag>
        </div>
        
        <el-input
          v-model="userInput"
          type="textarea"
          :rows="3"
          placeholder="请输入消息..."
          @keydown.enter="handleEnter"
        ></el-input>
        <el-button type="primary" @click="sendMessage" :loading="isLoading">发送 (Enter/Shift+Enter换行)</el-button>
      </div>
    </div>
    
    <!-- 新建会话对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建会话" width="400px">
      <el-input
        v-model="newConversationTitle"
        placeholder="请输入会话标题"
        @keyup.enter="createConversation"
      ></el-input>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showCreateDialog = false">取消</el-button>
          <el-button type="primary" @click="createConversation">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'

// Markdown 渲染和代码高亮
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

// 配置 marked 支持代码高亮
marked.setOptions({
  highlight: function (code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (__) {}
    }
    return '' // 使用默认的转义
  },
  breaks: true, // 支持换行
  gfm: true,    // 支持 GitHub Flavored Markdown
  headerIds: false // 不生成 header id
})

// Markdown 渲染函数
const renderMarkdown = (text) => {
  if (!text) return ''
  return marked(text)
}

const router = useRouter()

// 聊天相关变量
const userInput = ref('')
const chatMessages = ref([])
const isLoading = ref(false)

// 会话相关变量
const conversations = ref([])
const currentConversationId = ref(null)
const showCreateDialog = ref(false)
const newConversationTitle = ref('')

// 客服问题分类相关变量
const categories = ref([
  { id: 1, name: '账户问题', description: '登录、注册、密码等' },
  { id: 2, name: '订单咨询', description: '下单、支付、物流等' },
  { id: 3, name: '产品咨询', description: '产品功能、使用方法等' },
  { id: 4, name: '售后问题', description: '退换货、维修等' },
  { id: 5, name: '其他问题', description: '其他咨询' }
])
const recentCategories = ref([])
const selectedCategory = ref('')

// 会话状态相关变量
const currentConversationStatus = ref('')

// 当前会话
const currentConversation = computed(() => {
  return conversations.value.find(c => c.id === currentConversationId.value)
})

// 格式化时间
const formatTime = (timeString) => {
  const date = new Date(timeString)
  const now = new Date()
  const diff = now - date
  
  // 小于1小时
  if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  }
  // 小于24小时
  if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  }
  // 小于7天
  if (diff < 604800000) {
    return `${Math.floor(diff / 86400000)}天前`
  }
  // 显示日期
  return date.toLocaleDateString()
}

// 加载会话列表
const loadConversations = async () => {
  try {
    const response = await axios.get('/api/conversations')
    conversations.value = response.data
    
    // 如果有会话，默认选择第一个
    if (conversations.value.length > 0 && !currentConversationId.value) {
      switchConversation(conversations.value[0].id)
    }
  } catch (error) {
    console.error('加载会话列表失败:', error)
    ElMessage.error('加载会话列表失败')
    // 如果认证失败，跳转到登录页
    if (error.response?.status === 401) {
      handleLogout()
    }
  }
}

// 加载聊天记录
const loadChatHistory = async (conversationId) => {
  if (!conversationId) return
  
  try {
    const response = await axios.get('/api/messages', {
      params: { conversation_id: conversationId }
    })
    chatMessages.value = response.data
    
    // 滚动到底部
    setTimeout(() => {
      const chatMessagesElement = document.querySelector('.chat-messages')
      if (chatMessagesElement) {
        chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight
      }
    }, 100)
  } catch (error) {
    console.error('加载聊天记录失败:', error)
    ElMessage.error('加载聊天记录失败')
    // 如果认证失败，跳转到登录页
    if (error.response?.status === 401) {
      handleLogout()
    }
  }
}

// 创建新会话
const createConversation = async () => {
  if (!newConversationTitle.value.trim()) {
    ElMessage.warning('请输入会话标题')
    return
  }
  
  try {
    const response = await axios.post('/api/conversations', {
      title: newConversationTitle.value.trim()
    })
    
    // 添加到会话列表
    conversations.value.unshift(response.data)
    
    // 切换到新会话
    switchConversation(response.data.id)
    
    // 关闭对话框
    showCreateDialog.value = false
    newConversationTitle.value = ''
    
    ElMessage.success('会话创建成功')
  } catch (error) {
    console.error('创建会话失败:', error)
    ElMessage.error('创建会话失败')
    // 如果认证失败，跳转到登录页
    if (error.response?.status === 401) {
      handleLogout()
    }
  }
}

// 删除会话
const deleteConversation = async (conversationId) => {
  try {
    await ElMessageBox.confirm('确定要删除这个会话吗？删除后将无法恢复。', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await axios.delete(`/api/conversations/${conversationId}`)
    
    // 从列表中移除
    conversations.value = conversations.value.filter(c => c.id !== conversationId)
    
    // 如果删除的是当前会话，选择第一个会话
    if (currentConversationId.value === conversationId) {
      currentConversationId.value = null
      chatMessages.value = []
      if (conversations.value.length > 0) {
        switchConversation(conversations.value[0].id)
      }
    }
    
    ElMessage.success('会话已删除')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除会话失败:', error)
      ElMessage.error('删除会话失败')
      // 如果认证失败，跳转到登录页
      if (error.response?.status === 401) {
        handleLogout()
      }
    }
  }
}

// 获取状态标签类型
const getStatusTagType = (status) => {
  switch (status) {
    case 'active':
      return 'success'
    case 'ended':
      return 'info'
    case 'archived':
      return 'warning'
    default:
      return 'default'
  }
}

// 获取状态文本
const getStatusText = (status) => {
  switch (status) {
    case 'active':
      return '进行中'
    case 'ended':
      return '已结束'
    case 'archived':
      return '已归档'
    default:
      return status
  }
}

// 切换会话
const switchConversation = (conversationId) => {
  currentConversationId.value = conversationId
  loadChatHistory(conversationId)
  
  // 更新当前会话状态
  const conversation = conversations.value.find(c => c.id === conversationId)
  if (conversation) {
    currentConversationStatus.value = conversation.status
  }
}

// 更新会话状态
const updateConversationStatus = async () => {
  if (!currentConversationId.value || !currentConversationStatus.value) {
    return
  }
  
  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`/api/conversations/${currentConversationId.value}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      body: JSON.stringify({
        status: currentConversationStatus.value
      })
    })
    
    if (response.ok) {
      ElMessage.success('会话状态已更新')
      
      // 更新本地会话列表
      const conversationIndex = conversations.value.findIndex(c => c.id === currentConversationId.value)
      if (conversationIndex !== -1) {
        conversations.value[conversationIndex].status = currentConversationStatus.value
      }
    } else {
      const errorText = await response.text()
      ElMessage.error(`更新会话状态失败: ${errorText}`)
    }
  } catch (error) {
    console.error('更新会话状态失败:', error)
    ElMessage.error('更新会话状态失败')
  }
}

// 处理回车键
const handleEnter = (event) => {
  // 如果没有按下Shift键，发送消息
  if (!event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
  // 如果按下Shift键，保持换行功能
}

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim()) {
    ElMessage.warning('请输入消息内容')
    return
  }
  
  if (!currentConversationId.value) {
    ElMessage.warning('请先选择或创建会话')
    return
  }
  
  isLoading.value = true
  const message = userInput.value.trim()
  userInput.value = ''
  
  try {
    // 创建临时的完整消息项（包含用户消息和AI回复）
    const tempMessage = {
      id: Date.now(),
      message: message,       // 用户消息
      response: '',           // AI回复（初始为空）
      created_at: new Date().toISOString(),
      user_id: null, // 临时消息，没有真实ID
      category: selectedCategory.value || '其他问题' // 添加分类信息
    }
    
    // 添加到聊天消息列表
    chatMessages.value.push(tempMessage)
    
    // 保存临时消息的索引，用于后续更新
    const messageIndex = chatMessages.value.length - 1
    
    // 滚动到底部
    setTimeout(() => {
      const chatMessagesElement = document.querySelector('.chat-messages')
      if (chatMessagesElement) {
        chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight
      }
    }, 100)
    
    // 获取token
    const token = localStorage.getItem('token')
    
    // 使用fetch API接收流式响应
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      body: JSON.stringify({
        user_input: message,
        conversation_id: currentConversationId.value,
        category: selectedCategory.value // 添加分类信息到请求体
      })
    })
    
    // 更新最近使用的分类
    if (selectedCategory.value) {
      // 如果分类已经存在于最近使用列表中，先移除
      const existingIndex = recentCategories.value.indexOf(selectedCategory.value)
      if (existingIndex !== -1) {
        recentCategories.value.splice(existingIndex, 1)
      }
      // 将分类添加到最近使用列表的开头
      recentCategories.value.unshift(selectedCategory.value)
      // 限制最近使用列表的长度为5
      if (recentCategories.value.length > 5) {
        recentCategories.value.pop()
      }
    }
    
    // 重置分类选择
    selectedCategory.value = ''
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(errorText || '发送消息失败')
    }
    
    // 处理流式响应
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      // 解码数据
      buffer += decoder.decode(value, { stream: true })
      
      // 按行处理数据
      let lines = buffer.split('\n')
      buffer = lines.pop() // 保存不完整的行
      
      for (const line of lines) {
        if (!line.trim()) continue
        
        // 解析SSE格式
        if (line.startsWith('data: ')) {
          const data = line.substring(6)
          
          // 检查是否为完成标记
          if (data === '[DONE]') {
            console.log('流式传输完成')
            break
          }
          
          console.log('接收到字符:', data)
          // 逐字添加到AI回复
          tempMessage.response += data
          
          // 使用数组索引更新，确保Vue的响应式系统能检测到变化
          chatMessages.value[messageIndex] = { ...tempMessage }
          
          // 滚动到底部
          setTimeout(() => {
            const chatMessagesElement = document.querySelector('.chat-messages')
            if (chatMessagesElement) {
              chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight
            }
          }, 0)
        }
      }
    }
    
    // 延迟重新加载聊天记录，让用户有时间看到逐字效果
    setTimeout(async () => {
      await loadChatHistory(currentConversationId.value)
      // 更新会话列表
      await loadConversations()
    }, 1000)
  } catch (error) {
    console.error('发送消息失败:', error)
    ElMessage.error('发送消息失败')
    // 如果认证失败，跳转到登录页
    if (error.response?.status === 401) {
      handleLogout()
    }
  } finally {
    isLoading.value = false
  }
}

// 退出登录
const handleLogout = () => {
  localStorage.removeItem('token')
  delete axios.defaults.headers.common['Authorization']
  ElMessage.success('已退出登录')
  router.push('/login')
}

// 组件挂载时加载会话列表
onMounted(() => {
  loadConversations()
})
</script>

<style scoped>
/* 聊天容器 */
.chat-container {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  background-color: #ffffff;
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
}

/* 左侧边栏 */
.sidebar {
  width: 300px;
  border-right: 1px solid #dee2e6;
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #dee2e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #ffffff;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #212529;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background-color: #ffffff;
}

/* 自定义滚动条样式 */
.conversation-list::-webkit-scrollbar,
.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.conversation-list::-webkit-scrollbar-track,
.chat-messages::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
}

.conversation-list::-webkit-scrollbar-thumb,
.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.conversation-list::-webkit-scrollbar-thumb:hover,
.chat-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

.conversation-item {
  padding: 12px 16px;
  margin-bottom: 8px;
  background-color: #ffffff;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.conversation-item:hover {
  background-color: #f8f9fa;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.conversation-item.active {
  background-color: #e3f2fd;
  border-left: 4px solid #007bff;
}

.conversation-title {
  font-size: 14px;
  font-weight: 500;
  color: #212529;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-time {
  font-size: 12px;
  color: #6c757d;
}

.conversation-item .el-button {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.conversation-item:hover .el-button {
  opacity: 1;
}

/* 右侧聊天区域 */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: #ffffff;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background-color: #ffffff;
  border-bottom: 1px solid #dee2e6;
  color: #212529;
}

.chat-header h2 {
  margin: 0;
  font-size: 20px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: #f8f9fa;
  color: #212529;
}

.chat-empty {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f8f9fa;
  color: #212529;
}

.message-item {
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-bubble {
  max-width: 80%;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.user-message {
  align-self: flex-end;
  background-color: #dcf8c6;
  color: #212529;
  border-bottom-right-radius: 4px;
}

.ai-message {
  align-self: flex-start;
  background-color: #ffffff;
  color: #212529;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.message-header {
  font-size: 14px;
  font-weight: 600;
}

.user-message .message-author {
  color: #25d366;
}

.ai-message .message-author {
  color: #007bff;
}

.message-content {
  font-size: 16px;
  line-height: 1.7;
  color: #212529;
}

.chat-input {
  padding: 20px;
  background-color: #ffffff;
  border-top: 1px solid #e9ecef;
}

.chat-input .el-input {
  margin-bottom: 12px;
  background-color: #ffffff;
  border-radius: 8px;
  overflow: hidden;
}

.chat-input .el-textarea__inner {
  background-color: #ffffff;
  color: #212529;
  border: 1px solid #ced4da;
  border-radius: 8px;
}

.chat-input .el-textarea__inner:focus {
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.2);
}

.chat-input .el-button {
  background-color: #007bff;
  border-color: #007bff;
  border-radius: 8px;
  font-weight: 600;
}

.chat-input .el-button:hover {
  background-color: #0056b3;
  border-color: #0056b3;
}

.chat-input .el-button:active {
  background-color: #004085;
  border-color: #004085;
}

.chat-input .el-button {
  width: 100%;
}

/* Markdown 样式 */
.chat-messages h1,
.chat-messages h2,
.chat-messages h3,
.chat-messages h4,
.chat-messages h5,
.chat-messages h6 {
  margin: 10px 0;
  font-weight: bold;
  color: #212529;
  border-bottom: 1px solid #e9ecef;
  padding-bottom: 5px;
}

.chat-messages h1 { font-size: 24px; }
.chat-messages h2 { font-size: 20px; }
.chat-messages h3 { font-size: 18px; }
.chat-messages h4 { font-size: 16px; }
.chat-messages h5 { font-size: 14px; }
.chat-messages h6 { font-size: 12px; }

.chat-messages p {
  margin: 10px 0;
  line-height: 1.6;
  color: #212529;
}

.chat-messages ul,
.chat-messages ol {
  margin: 10px 0;
  padding-left: 20px;
  color: #212529;
}

.chat-messages li {
  margin: 5px 0;
}

.chat-messages blockquote {
  margin: 10px 0;
  padding: 10px 15px;
  border-left: 3px solid #007bff;
  background-color: #e9ecef;
  color: #495057;
}

.chat-messages pre {
  margin: 10px 0;
  padding: 15px;
  background-color: #f8f9fa;
  color: #212529;
  border-radius: 4px;
  overflow-x: auto;
  font-family: 'Courier New', Courier, monospace;
  border: 1px solid #dee2e6;
}

.chat-messages code {
  padding: 2px 4px;
  background-color: #e9ecef;
  border-radius: 3px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
  color: #dc3545;
}

.chat-messages pre code {
  background-color: transparent;
  padding: 0;
  color: inherit;
}

.chat-messages img {
  max-width: 100%;
  height: auto;
  margin: 10px 0;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.chat-messages table {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0;
  background-color: #ffffff;
}

.chat-messages th,
.chat-messages td {
  border: 1px solid #dee2e6;
  padding: 8px;
  text-align: left;
  color: #212529;
}

.chat-messages th {
  background-color: #f8f9fa;
  font-weight: bold;
}

/* 分类选择器样式 */
.category-selector {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.category-desc {
  font-size: 12px;
  color: #6c757d;
  margin-left: 8px;
}

.recent-category {
  cursor: pointer;
  margin-bottom: 8px;
  transition: all 0.3s ease;
}

.recent-category:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* 消息分类标签样式 */
.message-category {
  margin-left: 12px;
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 10px;
}

/* 会话列表样式增强 */
.conversation-item {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  margin-bottom: 8px;
  background-color: #ffffff;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.conversation-main {
  flex: 1;
  min-width: 0;
}

.conversation-title-container {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.conversation-title {
  font-size: 14px;
  font-weight: 500;
  color: #212529;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.conversation-status {
  margin-left: auto;
}

.conversation-last-message {
  font-size: 12px;
  color: #6c757d;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #9ca3af;
}

.message-count {
  background-color: #f3f4f6;
  color: #6b7280;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 11px;
}

/* 聊天头部样式增强 */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #dee2e6;
  background-color: #ffffff;
}

.chat-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-header-left h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #212529;
}

.header-status-tag {
  font-size: 12px;
}

.chat-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .chat-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
  
  .chat-header-left,
  .chat-header-right {
    justify-content: space-between;
  }
  
  .conversation-title-container {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  .conversation-status {
    align-self: flex-start;
  }
}
</style>