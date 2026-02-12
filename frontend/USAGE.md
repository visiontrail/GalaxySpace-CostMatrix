# CostMatrix 前端使用指南

## 📋 项目概述

CostMatrix 是一个企业管理驾驶舱前端应用，基于 React + TypeScript + Ant Design Pro + ECharts 构建，用于可视化展示企业考勤、差旅数据分析结果。

## 🚀 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

前端将运行在 `http://localhost:5173`

### 3. 构建生产版本

```bash
npm run build
```

## 📦 技术栈

- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Ant Design 5** - UI 组件库
- **@ant-design/pro-components** - 高级组件
- **ECharts 5** - 数据可视化
- **React Router 6** - 路由管理
- **Axios** - HTTP 客户端
- **Vite** - 构建工具

## 📊 功能模块

### 1. 数据看板 (Dashboard)

**路由**: `/`

**功能**:
- 📈 核心指标展示（总成本、平均工时、异常数量）
- 🥧 部门成本分布饼图
- 📊 项目成本排名柱状图
- ⏰ 部门平均工时柱状图
- 🎯 部门人数与成本关系散点图
- 📋 部门统计详细表格
- 📋 项目成本详细表格
- ⚠️ 异常记录详细表格
- 💾 导出分析结果功能

**数据结构**: 基于 `AnalysisResult` 类型

```typescript
interface AnalysisResult {
  summary: {
    total_cost: number
    avg_work_hours: number
    anomaly_count: number
  }
  department_stats: Array<{
    dept: string
    cost: number
    avg_hours: number
    headcount: number
  }>
  project_top10: Array<{
    code: string
    name: string
    cost: number
  }>
  anomalies: Array<{
    date: string
    name: string
    dept: string
    type: string
    detail: string
  }>
}
```

### 2. 文件上传 (Upload)

**路由**: `/upload`

**功能**:
- 📤 拖拽上传 Excel 文件
- 🔍 文件格式验证（仅支持 .xlsx, .xls）
- 📏 文件大小限制（最大 50MB）
- 📊 上传进度显示
- 🔄 自动触发数据分析
- ✅ 分析结果预览
- 🚀 自动跳转到数据看板

**支持的 Sheet 名称**:
- `状态明细` - 考勤数据
- `机票` - 机票差旅明细
- `酒店` - 酒店差旅明细
- `火车票` - 火车票差旅明细

## 🔌 API 对接

### API 基础地址

开发环境: `http://localhost:8000/api`
生产环境: `/api` (使用反向代理)

### API 接口

#### 1. 上传文件

```
POST /api/upload
Content-Type: multipart/form-data

Body: FormData { file: File }

Response: {
  success: boolean
  message: string
  data: {
    file_path: string
    file_size: number
    sheets: string[]
  }
}
```

#### 2. 分析数据

```
POST /api/analyze?file_path={path}

Response: {
  success: boolean
  message: string
  data: AnalysisResult
}
```

#### 3. 导出结果

```
POST /api/export?file_path={path}
Response: Blob (Excel 文件)
```

#### 4. 健康检查

```
GET /api/health

Response: {
  status: "ok"
  timestamp: string
}
```

## 🎨 UI/UX 特性

### 设计原则
- ✨ 现代化、简洁的界面设计
- 📱 响应式布局，支持移动端
- 🎯 一目了然的数据可视化
- 🚀 流畅的交互体验
- ♿ 良好的可访问性

### 交互特性
- 悬停效果增强
- 平滑的过渡动画
- 实时加载状态反馈
- 友好的错误提示
- 自动保存与恢复数据

### 颜色主题
- 主色调: `#1890ff` (蓝色)
- 成功色: `#52c41a` (绿色)
- 警告色: `#faad14` (橙色)
- 错误色: `#f5222d` (红色)

## 📁 项目结构

```
frontend/
├── src/
│   ├── types/           # TypeScript 类型定义
│   │   └── index.ts     # 核心类型
│   ├── services/        # API 服务层
│   │   └── api.ts       # API 请求封装
│   ├── pages/           # 页面组件
│   │   ├── Dashboard.tsx  # 数据看板页面
│   │   └── Upload.tsx     # 文件上传页面
│   ├── layouts/         # 布局组件
│   │   └── MainLayout.tsx # 主布局
│   ├── App.tsx          # 应用入口
│   ├── App.css          # 全局样式
│   └── main.tsx         # React 入口
├── package.json         # 依赖配置
├── vite.config.ts       # Vite 配置
├── tsconfig.json        # TypeScript 配置
└── index.html           # HTML 模板
```

## 🔧 开发指南

### 添加新页面

1. 在 `src/pages/` 创建新组件
2. 在 `src/App.tsx` 添加路由
3. 在 `src/layouts/MainLayout.tsx` 添加菜单项

### 添加新的 API 接口

1. 在 `src/types/index.ts` 定义数据类型
2. 在 `src/services/api.ts` 添加 API 方法
3. 在组件中导入并使用

### 添加新的图表

```typescript
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

const option: EChartsOption = {
  // ECharts 配置
}

<ReactECharts option={option} style={{ height: 400 }} />
```

## 🐛 常见问题

### Q: 本地开发时 API 请求失败？

**A**: 确保后端服务运行在 `http://localhost:8000`，Vite 配置了代理转发。

### Q: 上传大文件失败？

**A**: 
1. 检查文件大小是否超过 50MB
2. 检查后端超时配置
3. 检查网络连接状态

### Q: 图表显示不正常？

**A**: 
1. 检查数据结构是否匹配
2. 检查 ECharts 配置是否正确
3. 清除浏览器缓存重试

### Q: 类型错误？

**A**: 确保 `src/types/index.ts` 中的类型定义与后端返回的数据结构一致。

## 📝 代码规范

- 使用 TypeScript 严格模式
- 遵循 ESLint 规则
- 使用函数式组件和 Hooks
- 使用明确的类型定义，避免 `any`
- 组件命名使用 PascalCase
- 文件命名使用 kebab-case

## 🚀 性能优化

- 使用 React.memo 缓存组件
- 使用 useMemo 和 useCallback 优化计算
- ECharts 图表使用 `notMerge` 和 `lazyUpdate`
- 表格使用虚拟滚动（大数据量）
- 图片懒加载

## 🔐 安全注意事项

- 所有 API 请求通过 HTTPS
- 敏感数据不存储在 localStorage
- 文件上传进行类型和大小验证
- XSS 防护（Ant Design 自动转义）

## 📞 技术支持

如有问题，请联系 GalaxySpace AI Team

---

**版本**: 1.0.0  
**最后更新**: 2026-01-05


