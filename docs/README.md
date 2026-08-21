# 数字油画生产设计中心 · Web V100

## 入口

- 页面文件：`docs/index.html`
- 设计目标：把数字油画项目近期确认规则与 `AGENTS.md` 的桌面生产规范统一到一个 Web 工作台。

## 已实现

- JPG/PNG 原图导入与预览
- 12 / 24 / 36 / 50 色目标选择
- 浏览器端轻量分色效果图
- 线稿边界预览
- 色卡预览
- 第一规则展示
- 自动 QC 检查面板
- 学习中心：reference_samples / negative_samples / corrections / parameter_profiles
- PNG 导出
- 响应式桌面/移动界面

## 生产参数

- 线稿：0.1 pt
- 线色：CMYK 40,100,100,100
- 编号字号：4.2 / 6 / 8 pt
- 效果图、线稿图、配色图共用 region_id / color_id
- 相邻色块共享唯一边界；禁止白缝、双线、交叉线、未闭合区域

## Web 与桌面核心边界

Web 端用于快速预览、参数管理、轻量分色、QC 面板与流程统一。生产级矢量共享边界、真实 PDF/SVG、精确编号放置、自有色库 Lab 匹配以及完整拓扑修复，应调用仓库桌面核心算法实现，禁止将整页栅格图包装成“矢量 PDF”。

## GitHub Pages

本目录使用纯 HTML/CSS/JavaScript，无构建依赖。合并后可以把 GitHub Pages Source 设置为 `main` 分支的 `/docs` 目录发布。
