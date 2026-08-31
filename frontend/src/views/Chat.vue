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
          <el-button @click="$router.push('/knowledge')">知识库</el-button>
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
              <el-tag v-if="msg.ragUsed" type="primary" size="small" effect="plain">知识库</el-tag>
            </div>
            <div class="message-content" v-html="renderMarkdown(msg.response)"></div>
            <!-- P5.2：RAG/Tool 状态进度（流式中间状态，done 后会被 onDone 重新加载历史覆盖） -->
            <div v-if="msg.statusSteps && msg.statusSteps.length" class="status-steps">
              <div v-for="(step, si) in msg.statusSteps" :key="si" class="status-step" :class="'step-' + step.type">
                <span class="step-icon">{{ step.type === 'rag' ? '📚' : step.type === 'tool' ? '🔧' : '⏳' }}</span>
                <span class="step-text">{{ step.text }}</span>
                <span v-if="step.ok !== undefined" class="step-ok">{{ step.ok ? '✓' : '✗' }}</span>
              </div>
            </div>
            <!-- RAG 参考来源（仅知识库命中时展示，citation 均来自真实检索） -->
            <div v-if="msg.citations && msg.citations.length" class="citation-panel">
              <div class="citation-title">参考来源</div>
              <div v-for="(c, ci) in msg.citations" :key="ci" class="citation-item">
                <span class="citation-icon">📄</span>
                <span class="citation-filename">{{ c.filename }}</span>
                <span class="citation-chunk">第 {{ c.chunk_index + 1 }} 个知识片段</span>
                <span class="citation-score">相似度 {{ (c.score * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div v-else class="chat-empty">
        <el-empty description="请选择或创建一个会话开始聊天"></el-empty>
      </div>
      
      <div class="chat-input" v-if="currentConversationId">
        <div class="input-status-row" v-if="streamingStatus">
          <!-- P5.2：流式状态指示 -->
          <span class="streaming-status" :class="'status-' + streamingStatus.type">
            <span v-if="streamingStatus.type === 'thinking'" class="status-dot status-dot-thinking">思考中</span>
            <span v-else-if="streamingStatus.type === 'generating'" class="status-dot status-dot-generating">生成中</span>
            <span v-else-if="streamingStatus.type === 'error'" class="status-dot status-dot-error">生成失败</span>
            <span v-else-if="streamingStatus.type === 'done'" class="status-dot status-dot-done">已完成</span>
            <span v-if="streamingStatus.text"> · {{ streamingStatus.text }}</span>
          </span>
          <!-- P5.2：Request ID（开发调试用） -->
          <span v-if="lastRequestId && isDev" class="request-id-tag">
            请求 ID：{{ lastRequestId }}
          </span>
        </div>
        <!-- AI自动分类 - 隐藏手动选择器 -->
        <div class="category-selector" style="display: none;">
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
          :disabled="isLoading"
          @keydown.enter="handleEnter"
        ></el-input>
        <div class="input-buttons">
          <!-- P5.2：停止生成按钮（仅流式中显示） -->
          <el-button 
            v-if="isLoading && chatAbortController" 
            type="danger" 
            plain 
            @click="stopGeneration"
          >停止生成</el-button>
          <el-button 
            type="primary" 
            @click="sendMessage" 
            :loading="isLoading" 
            :disabled="isLoading"
          >发送 (Enter/Shift+Enter换行)</el-button>
        </div>
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
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'

// 工程化 API 封装
import { logout, syncGlobalAuthorization } from '../api/auth'
import {
  getConversations,
  createConversation as apiCreateConversation,
  deleteConversation as apiDeleteConversation,
  updateConversationStatus as apiUpdateStatus,
  getMessages,
} from '../api/conversations'
import { aiClassify, chatStream } from '../api/chat'

// Markdown 渲染和代码高亮
import { marked } from 'marked'
// P5.2：highlight.js 只加载 core + 常用语言，替代全量（全量 ~900KB → core 约 50KB）
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import python from 'highlight.js/lib/languages/python'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import plaintext from 'highlight.js/lib/languages/plaintext'
import 'highlight.js/styles/github.css'

// P5.2：注册常用语言
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('plaintext', plaintext)

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
  // P5.1 P2-1：轻量 XSS 防护（不引入新依赖）：移除 script 标签与 on* 事件属性，
  // 覆盖常见 XSS 注入向量；客服场景下 Markdown 渲染安全
  return marked(text)
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/\son\w+\s*=\s*"[^"]*"/gi, '')
    .replace(/\son\w+\s*=\s*'[^']*'/gi, '')
}

const router = useRouter()

// P5.2：开发环境标记（模板中不可直接使用 import.meta.env，故在此暴露）
const isDev = import.meta.env.DEV

// 聊天相关变量
const userInput = ref('')
const chatMessages = ref([])
const isLoading = ref(false)

// P5.2：流式状态（thinking/generating/done/error）与中间文本
const streamingStatus = ref(null)
// P5.2：最近一次请求的 Request ID（开发调试展示用）
const lastRequestId = ref('')

// P5.1 P2-3：SSE 流式请求的 AbortController，组件卸载时取消未完成的请求
let chatAbortController = null
// P5.2：标记本次流式是否被用户主动取消（AbortError 正常路径）
let _userAborted = false

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
    const data = await getConversations()
    conversations.value = data
    
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
    const data = await getMessages(conversationId)
    chatMessages.value = data
    
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
    const data = await apiCreateConversation(newConversationTitle.value.trim())
    
    // 添加到会话列表
    conversations.value.unshift(data)
    
    // 切换到新会话
    switchConversation(data.id)
    
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
    
    await apiDeleteConversation(conversationId)
    
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
    const response = await apiUpdateStatus(currentConversationId.value, currentConversationStatus.value)
    
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

// 滚动聊天区到底部
const scrollToBottom = (delay = 0) => {
  setTimeout(() => {
    const chatMessagesElement = document.querySelector('.chat-messages')
    if (chatMessagesElement) {
      chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight
    }
  }, delay)
}

// P5.2：流式状态管理
const setStreamingStatus = (type, text = '') => {
  streamingStatus.value = type ? { type, text } : null
  // done 后延迟清除状态条（让用户看到"已完成"状态）
  if (type === 'done') {
    setTimeout(() => { streamingStatus.value = null }, 2000)
  } else if (type === 'error') {
    setTimeout(() => { streamingStatus.value = null }, 5000)
  }
}

// P5.2：停止生成 —— abort SSE，保留已生成内容，前端结束 loading
const stopGeneration = () => {
  _userAborted = true
  if (chatAbortController) {
    chatAbortController.abort()
    chatAbortController = null
  }
  setStreamingStatus('error', '已手动停止')
}

// P5.2：Tool 名称 → 中文状态文案
const _TOOL_LABEL = {
  order_query: '订单查询',
  logistics_query: '物流查询',
  human_service: '人工客服转接',
}

// P5.2：RAG reason → 中文状态文案
const _RAG_LABEL = {
  ok: '检索到相关知识',
  low_similarity: '知识相似度较低',
  no_kb: '未配置知识库',
  empty_kb: '知识库为空',
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

  // P5.2：防止重复发送
  if (isLoading.value) {
    ElMessage.warning('正在生成中，请稍候')
    return
  }

  isLoading.value = true
  _userAborted = false
  setStreamingStatus('thinking')
  const message = userInput.value.trim()
  userInput.value = ''

  try {
    // 1. 先调用AI分类接口（request 封装，自动带 token）
    let category = '其他问题'
    try {
      const classifyResult = await aiClassify(message)
      category = classifyResult.category || '其他问题'
    } catch (err) {
      console.warn('AI 分类失败，使用默认分类：其他问题', err)
    }

    // 创建临时的完整消息项（包含用户消息和AI回复）
    const tempMessage = {
      id: Date.now(),
      message: message,       // 用户消息
      response: '',           // AI回复（初始为空）
      created_at: new Date().toISOString(),
      user_id: null,
      category: category,
      ragUsed: false,         // P2.2：RAG 是否命中
      citations: [],          // P2.2：知识库引用来源
      statusSteps: [],        // P5.2：RAG/Tool 状态步骤（展示用，done 后被覆盖）
    }

    // 添加到聊天消息列表
    chatMessages.value.push(tempMessage)

    // 保存临时消息的索引，用于后续更新
    const messageIndex = chatMessages.value.length - 1
    scrollToBottom(100)

    // 2. 发送聊天请求（事件化 SSE 流式）
    chatAbortController = new AbortController()
    try {
      await chatStream(
        {
          user_input: message,
          conversation_id: currentConversationId.value,
          category: category,
        },
        {
          // P5.2：Request ID 捕获
          onRequestId: (rid) => {
            lastRequestId.value = rid
          },
          // 服务端确认的分类
          onCategory: (data) => {
            if (data && data.category) {
              tempMessage.category = data.category
              chatMessages.value[messageIndex] = { ...tempMessage }
            }
          },
          // RAG 路由结论
          onRag: (data) => {
            if (!data) return
            tempMessage.ragUsed = !!data.used
            // P5.2：RAG 状态步骤
            const ragText = data.used
              ? `已参考知识库 · 相似度 ${((data.top_score || 0) * 100).toFixed(0)}%`
              : (_RAG_LABEL[data.reason] || '知识库未命中')
            tempMessage.statusSteps.push({ type: 'rag', text: ragText, ok: !!data.used })
            setStreamingStatus('thinking', data.used ? '检索知识库中…' : '')
            chatMessages.value[messageIndex] = { ...tempMessage }
          },
          // 知识库引用来源
          onCitation: (data) => {
            tempMessage.citations.push(data)
            chatMessages.value[messageIndex] = { ...tempMessage }
          },
          // P5.2：Tool 开始执行
          onToolStart: (data) => {
            if (!data) return
            const label = _TOOL_LABEL[data.tool] || data.tool
            tempMessage.statusSteps.push({ type: 'tool', text: `${label}中…`, ok: undefined })
            setStreamingStatus('thinking', `${label}中…`)
            chatMessages.value[messageIndex] = { ...tempMessage }
          },
          // P5.2：Tool 执行完成
          onToolResult: (data) => {
            if (!data) return
            const label = _TOOL_LABEL[data.tool] || data.tool
            // 更新最后一个 tool step 的 ok 状态
            const lastStep = tempMessage.statusSteps[tempMessage.statusSteps.length - 1]
            if (lastStep && lastStep.type === 'tool' && !lastStep.ok) {
              lastStep.ok = !!data.ok
              lastStep.text = data.ok ? `${label}完成` : `${label}失败`
            } else {
              tempMessage.statusSteps.push({
                type: 'tool', text: data.ok ? `${label}完成` : `${label}失败`, ok: !!data.ok,
              })
            }
            chatMessages.value[messageIndex] = { ...tempMessage }
          },
          // 拼接 AI 回复片段
          onMessage: (chunk) => {
            tempMessage.response += chunk
            // 首次收到 message 时切换为 generating 状态
            if (streamingStatus.value?.type === 'thinking') {
              setStreamingStatus('generating')
            }
            chatMessages.value[messageIndex] = { ...tempMessage }
            scrollToBottom()
          },
          // 流内错误事件
          onError: (err) => {
            const msg = err?.message || ''
            // P5.2：友好错误提示，不暴露 traceback
            if (msg.includes('402') || msg.includes('Insufficient Balance')) {
              ElMessage.warning('AI 服务余额不足，已切换为备用回复')
            } else if (msg.includes('NetworkError') || msg.includes('Failed to fetch') || msg.includes('Network')) {
              ElMessage.error('网络连接异常，请稍后重试')
            } else {
              ElMessage.error('AI 服务暂时不可用，请稍后重试')
            }
            setStreamingStatus('error', '生成失败')
          },
          // done 事件
          onDone: async () => {
            setStreamingStatus('done')
            try {
              await loadChatHistory(currentConversationId.value)
              await loadConversations()
            } catch (e) {
              console.warn('刷新历史失败（done 后）', e)
            }
          },
        },
        chatAbortController.signal
      )
    } finally {
      chatAbortController = null
    }

    // 更新最近使用的分类
    if (tempMessage.category) {
      category = tempMessage.category
    }
    if (category) {
      const existingIndex = recentCategories.value.indexOf(category)
      if (existingIndex !== -1) {
        recentCategories.value.splice(existingIndex, 1)
      }
      recentCategories.value.unshift(category)
      if (recentCategories.value.length > 5) {
        recentCategories.value.pop()
      }
    }
  } catch (error) {
    // P5.2：用户主动取消不算错误
    if (_userAborted) {
      setStreamingStatus('done')
      return
    }
    console.error('发送消息失败:', error)
    // P5.2：友好错误提示，不暴露 traceback
    const msg = error?.message || ''
    if (msg.includes('NetworkError') || msg.includes('Failed to fetch') || msg.includes('Network')) {
      ElMessage.error('网络连接异常，请稍后重试')
    } else if (error.response?.status === 401) {
      ElMessage.error('登录已过期，请重新登录')
      handleLogout()
    } else {
      ElMessage.error('发送消息失败，请稍后重试')
    }
    setStreamingStatus('error', '发送失败')
  } finally {
    isLoading.value = false
  }
}

// 退出登录
const handleLogout = () => {
  logout()
  // 兼容老逻辑：手动清一次全局 axios header
  delete axios.defaults.headers.common['Authorization']
  syncGlobalAuthorization()
  ElMessage.success('已退出登录')
  router.push('/login')
}

// 组件挂载时加载会话列表
onMounted(() => {
  loadConversations()
})

// P5.1 P2-3：组件卸载时取消未完成的 SSE 流，避免回调操作已卸载的 ref
onUnmounted(() => {
  if (chatAbortController) {
    chatAbortController.abort()
    chatAbortController = null
  }
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

/* RAG 参考来源（P2.2） */
.citation-panel {
  margin-top: 10px;
  padding: 8px 10px;
  border-top: 1px dashed #e4e7ed;
}

.citation-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
  font-weight: 600;
}

.citation-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
  line-height: 1.8;
}

.citation-filename {
  color: #409eff;
}

.citation-chunk {
  color: #909399;
}

.citation-score {
  margin-left: auto;
  color: #67c23a;
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

/* P5.2：流式状态条 */
.input-status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

.streaming-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.status-dot {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.status-dot-thinking {
  background-color: #ecf5ff;
  color: #409eff;
  animation: pulse 1.5s ease-in-out infinite;
}

.status-dot-generating {
  background-color: #f0f9eb;
  color: #67c23a;
}

.status-dot-error {
  background-color: #fef0f0;
  color: #f56c6c;
}

.status-dot-done {
  background-color: #f4f4f5;
  color: #909399;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* P5.2：Request ID 调试标签 */
.request-id-tag {
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: #909399;
  background-color: #f4f4f5;
  padding: 2px 8px;
  border-radius: 4px;
}

/* P5.2：按钮组 */
.input-buttons {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.input-buttons .el-button {
  flex: 1;
}

/* P5.2：Tool/RAG 状态步骤 */
.status-steps {
  margin-top: 10px;
  padding: 8px 10px;
  border-top: 1px dashed #e4e7ed;
  background-color: #fafafa;
  border-radius: 6px;
}

.status-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
}

.step-icon {
  font-size: 14px;
}

.step-text {
  flex: 1;
}

.step-ok {
  font-weight: 600;
}

.step-rag .step-ok { color: #67c23a; }
.step-tool .step-ok { color: #67c23a; }
.step-tool.step-fail .step-ok { color: #f56c6c; }
</style>