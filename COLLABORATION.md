# V10 ChatGPT + Copilot Chat 协作指南

## 项目概况
**数字油画生产流水线 V10**  
核心算法完成，进入功能扩展与优化阶段。

## 协作流程

### 分支策略
- `main`: 生产就绪版本
- `v10-core`: V10 稳定基线
- `v10-boundary-dedup`: 共享边界去重（消除双线）
- `v10-bezier`: Bézier 曲线平滑与锚点精简
- `v10-palette-lib`: 自有色库编号匹配系统
- `v10-pdf-export`: PDF 三页生产导出

### 开发流程

#### ChatGPT 生成代码
1. ChatGPT 在对应功能分支生成代码
2. 代码进入 `src/pbn_v10/modules/` 或 `src/pbn_v10/exporters.py`
3. 更新 `pyproject.toml` 依赖（如需）
4. 自动更新 QA 报告和 manifest

#### Copilot Chat 集成与审核
1. 验证代码质量和性能
2. 确保与 pipeline.py 兼容性
3. 整合到主流程
4. 创建 PR 并进行审核

#### 代码规范
```python
# 必须遵循的约定
- 类型注解：from __future__ import annotations
- 文档字符串：完整的 docstring
- 测试覆盖：unit test
- 性能指标：处理时间和内存占用
```

## 下一批优先级

### 1️⃣ v10-boundary-dedup (共享边界去重)
**目标**: 消除相邻色块间的双线现象  
**关键**: 建立边界图、合并相邻边界、去重重复线段

### 2️⃣ v10-bezier (Bézier 平滑曲线)
**目标**: 优化线稿质量，减少锚点  
**关键**: 轮廓 → Bézier 拟合 → 锚点精简

### 3️⃣ v10-palette-lib (自有色库)
**目标**: 支持自定义调色板编号  
**关键**: 色库管理、编号映射、格式导入

### 4️⃣ v10-pdf-export (PDF 三页)
**目标**: 生成生产级 PDF（线稿 + 效果 + 配色表）  
**关键**: 分页、分层、PDF 压缩

## 代码集成检查清单

- [ ] 类型注解完整
- [ ] 单元测试通过
- [ ] QA 报告更新
- [ ] manifest.json 同步
- [ ] 文档注释齐全
- [ ] 性能基准测试
- [ ] 与 V10Config 集成

## 文件位置约定

```
src/pbn_v10/
├── pipeline.py           # 核心流程（已稳定）
├── exporters.py          # 导出器（保持增量更新）
├── cli.py                # CLI 接口（保持稳定）
├── modules/              # 新功能模块（按功能分组）
│   ├── boundary_dedup.py
│   ├── bezier_smooth.py
│   ├── palette_lib.py
│   └── pdf_export.py
└── __init__.py
```

## 提交规范

```
feat(v10-boundary-dedup): implement shared boundary deduplication
- Remove duplicate edges between adjacent color regions
- Optimize boundary graph representation
- Add performance benchmark

Closes: #<issue_number>
```

## 质量指标

| 指标 | 目标 |
|------|------|
| 单元测试覆盖率 | > 85% |
| 处理时间 | < 5s (1000x1000 图像) |
| 内存占用 | < 500MB |
| QA 报告通过率 | 100% |

---

**更新**: 2026-08-20  
**维护者**: 117573414lyr-design + ChatGPT Codex + Copilot Chat
