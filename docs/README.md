# 数字油画生产设计中心 · Web V110

V110 是当前网站完成版，目标是把近期确认的数字油画生产规则集中到一个可以直接打开使用的 Web 工作台。

## 已完成

- JPG / PNG / WEBP 导入、拖放、缩放处理
- 12 / 24 / 36 / 50 色目标选择
- Lab 空间 K-means 分色
- 自有色库 CSV 导入
- 自有色库 Lab / ΔE2000 映射
- 连通区域分析
- 小碎块按真实相邻关系自动合并
- 区域内部安全编号落点
- 4.2 / 6 / 8 pt 编号预览
- 同一 `colorIndex` 生成效果图与编号线稿
- PNG 导出
- SVG `path + text` 真矢量导出
- 三页 PDF 直接生成
  1. 效果图：矢量色带填充
  2. 编号线稿：矢量线 + 独立文字对象
  3. 配色图：矢量色块 + 独立文字对象
- 色卡 CSV（RGB + Lab）
- 项目 JSON 保存 / 恢复
- PASS / WARN / FAIL 自动 QC
- 桌面与手机响应式界面
- GitHub Actions JavaScript 语法与静态文件检查
- GitHub Pages 自动部署工作流

## 固定生产参数

- 线稿目标：`0.1 pt`
- 线色目标：`CMYK 40,100,100,100`
- 编号字号：`4.2 / 6 / 8 pt`
- 色差：`Lab / ΔE2000`
- 效果图、线稿、配色图共享同一套 `colorIndex / color_id`
- 相邻色块共享边界，禁止白缝、双线、重叠线和错误编号

## 自有色库 CSV

```csv
color_id,r,g,b
A001,213,189,160
A002,122,91,71
A003,55,42,38
```

网站内也提供“下载 CSV 模板”。

## 文件结构

- `docs/index.html`：网站 UI
- `docs/styles.css`：响应式样式
- `docs/app.js`：分色、区域、编号、色库、QC、导出逻辑
- `docs/pdf.js`：三页矢量 PDF 写入器
- `docs/.nojekyll`：GitHub Pages 静态发布
- `.github/workflows/web-v110-check.yml`：自动检查
- `.github/workflows/pages.yml`：GitHub Pages 自动发布

## 与 Windows 桌面生产核心的边界

Web V110 已完成可用网站和主要生产流程。Illustrator 原生 `.ai`、复杂孔洞拓扑、极高精度 Bézier 锚点控制、字体嵌入、专业 CMYK 印前配置等继续由 Windows 桌面核心负责，不在网页端伪装实现。
