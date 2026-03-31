# AI自动分类功能实现方案

## 1. AI自动分类流程设计

```
用户输入问题 → 前端发送分类请求 → AI分类接口 → 智谱GLM API判断分类 → 返回分类结果 → 前端自动填充分类字段 → 发送聊天请求 → AI回复 → 显示分类标签
```

### 详细流程说明：
1. **用户输入问题**：用户在聊天界面输入问题
2. **前端发送分类请求**：前端调用`/ai-classify`接口，将用户问题发送给后端
3. **AI分类接口处理**：后端接收请求，调用智谱GLM API进行分类
4. **智谱GLM API判断分类**：使用精心设计的Prompt引导AI返回准确的分类结果
5. **返回分类结果**：后端将分类结果返回给前端
6. **前端自动填充分类字段**：前端使用AI返回的分类结果，不再需要用户手动选择
7. **发送聊天请求**：前端将包含自动分类结果的聊天请求发送给后端
8. **AI回复**：后端处理聊天请求，返回AI回复
9. **显示分类标签**：前端在消息中自动显示AI判断的分类标签

## 2. AI分类Prompt设计

### 输入：
用户问题（如："我忘记密码了，怎么重置？"）

### 输出：
必须匹配现有分类（账户问题 / 订单咨询 / 产品咨询 / 售后问题 / 其他问题）

### Prompt内容：
```
你是一个客服系统的分类助手，请根据用户的问题将其分类为以下类别之一：
账户问题, 订单咨询, 产品咨询, 售后问题, 其他问题

请严格按照要求进行分类：
1. 只返回分类结果，不要添加任何解释或说明
2. 必须从给定的分类列表中选择，不能自创分类
3. 如果无法确定分类，返回'其他问题'

用户问题：{user_input}
分类结果：
```

## 3. 数据结构复用方案

### 现有数据结构：
- `chat_messages`表已包含`category`字段，用于存储问题分类
- `categories`表已包含预设的分类数据（账户问题、订单咨询、产品咨询、售后问题、其他问题）

### 复用方案：
- **不新增新表**：直接使用现有表结构
- **直接写入原有分类字段**：将AI分类结果写入`chat_messages`表的`category`字段
- **保持向后兼容**：保留原有的`category`字段，确保历史数据不受影响

## 4. 前端改造方案（Vue3）

### 核心改造点：

1. **隐藏手动分类选择器**：
```vue
<div class="category-selector" style="display: none;">
  <!-- 分类选择器内容 -->
</div>
```

2. **发送消息前调用分类接口**：
```javascript
// 1. 先调用AI分类接口
const classifyResponse = await fetch('/api/ai-classify', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': token ? `Bearer ${token}` : ''
  },
  body: JSON.stringify({
    user_input: message
  })
})

let category = '其他问题' // 默认分类
if (classifyResponse.ok) {
  const classifyResult = await classifyResponse.json()
  category = classifyResult.category
}
```

3. **使用AI分类结果**：
```javascript
// 2. 使用分类结果发送聊天请求
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': token ? `Bearer ${token}` : ''
  },
  body: JSON.stringify({
    user_input: message,
    conversation_id: currentConversationId.value,
    category: category // 使用AI分类结果
  })
})
```

4. **自动显示分类标签**：
- 保持原有消息显示逻辑，分类标签会自动显示在用户消息旁边

## 5. 后端接口设计（FastAPI）

### 新增接口：`/ai-classify`

#### 请求方法：
POST

#### 请求体：
```json
{
  "user_input": "我忘记密码了，怎么重置？"
}
```

#### 响应体：
```json
{
  "category": "账户问题"
}
```

#### 接口实现：
```python
@app.post("/ai-classify", response_model=AIClassifyResponse)
def ai_classify(request: AIClassifyRequest, db: Session = Depends(get_db)):
    try:
        # 获取所有有效分类
        categories = db.query(Category).all()
        category_names = [cat.name for cat in categories]
        
        # 构造分类Prompt
        classify_prompt = f"""你是一个客服系统的分类助手，请根据用户的问题将其分类为以下类别之一：
{', '.join(category_names)}

请严格按照要求进行分类：
1. 只返回分类结果，不要添加任何解释或说明
2. 必须从给定的分类列表中选择，不能自创分类
3. 如果无法确定分类，返回'其他问题'

用户问题：{request.user_input}
分类结果："""
        
        # 调用智谱GLM API进行分类
        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "glm-4",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的客服分类助手，只能输出指定的分类名称。"
                },
                {
                    "role": "user",
                    "content": classify_prompt
                }
            ],
            "temperature": 0.1,  # 降低温度，使结果更稳定
            "max_tokens": 10  # 限制输出长度
        }
        
        response = requests.post(ZHIPU_API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        # 提取分类结果
        category = result["choices"][0]["message"]["content"].strip()
        
        # 验证分类结果是否有效
        if category not in category_names:
            category = "其他问题"  # 默认分类
        
        return AIClassifyResponse(category=category)
    except requests.RequestException as e:
        print(f"调用GLM API错误: {str(e)}")
        # 降级方案：基于关键词的简单分类
        user_input = request.user_input.lower()
        
        if any(keyword in user_input for keyword in ["登录", "注册", "密码", "账户", "账号"]):
            category = "账户问题"
        elif any(keyword in user_input for keyword in ["订单", "支付", "物流", "发货", "运费"]):
            category = "订单咨询"
        elif any(keyword in user_input for keyword in ["产品", "功能", "使用", "怎么", "如何"]):
            category = "产品咨询"
        elif any(keyword in user_input for keyword in ["退货", "换货", "维修", "售后", "退款"]):
            category = "售后问题"
        else:
            category = "其他问题"
        
        return AIClassifyResponse(category=category)
    except Exception as e:
        print(f"分类错误: {str(e)}")
        return AIClassifyResponse(category="其他问题")
```

## 6. 最小实现方案（MVP）

### 实现时间：1天

### 实现步骤：

#### 后端实现（2-3小时）：
1. **新增Pydantic模型**：
   - `AIClassifyRequest`：分类请求模型
   - `AIClassifyResponse`：分类响应模型

2. **实现`/ai-classify`接口**：
   - 调用智谱GLM API进行分类
   - 实现降级方案（关键词分类）
   - 返回分类结果

#### 前端实现（2-3小时）：
1. **修改`sendMessage`函数**：
   - 发送消息前先调用分类接口
   - 使用AI分类结果填充分类字段

2. **隐藏分类选择器**：
   - 保持分类标签显示功能

3. **更新分类管理逻辑**：
   - 使用AI分类结果更新最近使用的分类

#### 测试与优化（2-3小时）：
1. **测试分类接口**：
   - 验证各种类型问题的分类准确性
   - 测试降级方案是否正常工作

2. **测试聊天流程**：
   - 验证分类标签是否正确显示
   - 验证聊天功能是否正常

3. **优化分类逻辑**：
   - 根据测试结果调整Prompt
   - 优化降级方案的关键词

### 不影响现有功能的保证：
1. **保持数据结构不变**：不新增表，不修改现有字段含义
2. **保持接口兼容性**：聊天接口保持不变，仅新增分类接口
3. **保持用户体验连续性**：仅隐藏分类选择器，保留分类标签显示
4. **实现降级方案**：当AI分类接口不可用时，自动切换到基于关键词的分类

## 7. 代码实现文件

### 后端文件：
- `backend/main.py`：新增AI分类接口

### 前端文件：
- `frontend/src/views/Chat.vue`：修改发送消息逻辑，隐藏分类选择器

### 测试文件：
- `test_ai_classify.py`：测试AI分类接口

### 文档文件：
- `AI_AUTO_CLASSIFY_IMPLEMENTATION.md`：实现方案文档

## 8. 运行与测试

### 启动后端服务：
```bash
cd backend
uvicorn main:app --reload
```

### 测试分类接口：
```bash
python test_ai_classify.py
```

### 启动前端服务：
```bash
cd frontend
npm run dev
```

## 9. 注意事项

1. **API Key配置**：确保在`.env`文件中配置了有效的智谱GLM API Key
2. **网络连接**：确保服务器可以访问智谱GLM API
3. **降级方案**：当智谱GLM API不可用时，系统会自动切换到基于关键词的分类
4. **分类准确性**：可以根据实际使用情况调整Prompt和关键词列表，提高分类准确性
5. **性能优化**：可以考虑缓存常用问题的分类结果，提高响应速度

## 10. 后续优化建议

1. **分类模型训练**：使用历史数据训练专门的分类模型，提高准确性
2. **多语言支持**：扩展分类功能，支持多语言问题分类
3. **动态分类更新**：支持管理员动态添加/修改分类，AI自动适应新分类
4. **分类统计分析**：添加分类统计功能，分析用户问题分布
5. **智能推荐分类**：结合用户历史行为，推荐可能的分类（如果需要恢复手动选择）

---

## 实现总结

本方案实现了完整的AI自动分类功能，具有以下特点：

1. **无缝集成**：完全基于现有系统进行增强，不影响现有功能
2. **用户友好**：用户无需手动选择分类，提高使用效率
3. **准确性高**：使用精心设计的Prompt引导AI返回准确的分类结果
4. **可靠性强**：实现了降级方案，确保系统稳定运行
5. **易于维护**：代码结构清晰，便于后续扩展和优化

该方案可以在1天内完成实现，满足MVP需求，同时为后续功能扩展提供了良好的基础。