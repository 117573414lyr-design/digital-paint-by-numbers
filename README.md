# digital-paint-by-numbers

Windows 本地数字油画生产软件，当前开发版本 **V6 / 0.6.0**。

当前开发分支：`feature/windows-v0.1`

> 本项目仍在持续生产化。V6 已把效果图、区域、编号、自有色库、SVG/PDF 和 QC 串成同一数据流水线；最终质量标准仍以根目录 `AGENTS.md` 为准。

## V6 已实现

### V1 基础分色

- PySide6 Windows 桌面 GUI
- JPG / PNG / JPEG / WEBP 导入
- RGB → CIE Lab → KMeans 分色
- 2–256 自定义色数
- 后台线程处理，避免 UI 主线程卡死

### V2 区域生产化

- 按颜色建立连通区域
- 稳定 `region_id`
- 区域邻接图
- 小碎块自动合并
- 合并策略同时考虑共享边界长度与颜色距离

### V3 线稿/编号基础

- 每个区域自动寻找内部最安全编号点
- 4.2 / 6 / 8 pt 自适应字号
- 检测无法容纳约 5 pt 编号的区域
- 轮廓矢量化基础

### V4 自有色库

- JSON 色库导入
- 保存正式色号、RGB、HEX、名称
- CIE Lab 色差匹配
- KMeans 临时序号与正式色号分离

### V5 矢量输出 + QC

- 效果图 PNG
- 可编辑 SVG 编号线稿
- 三页矢量 PDF：效果图 / 编号线稿 / 配色页
- 线稿目标 0.1 pt
- 线条目标 CMYK 40,100,100,100
- QC PASS / WARN / FAIL
- 检查区域覆盖、碎块、编号容量、编号覆盖、色库映射、邻接拓扑

### V6 生产流水线整合

- 效果图、线稿、编号、配色、PDF 共用同一套 `region_id / color_id`
- 内部共享边界只生成一次，避免双线/重复边界
- 最小区域阈值可在 GUI 中调整
- 可直接导出 QC JSON
- 为后续曲线平滑、参考 AI 样本学习、项目文件和 EXE 打包保留模块接口

## Windows 安装

建议 Windows 10/11 + Python 3.12 64-bit。

```powershell
git clone https://github.com/117573414lyr-design/digital-paint-by-numbers.git
cd digital-paint-by-numbers
git checkout feature/windows-v0.1
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,build]"
```

## 启动

```powershell
digital-paint
```

或：

```powershell
python -m digital_paint.app
```

## V6 使用流程

1. 点击 **导入原图**。
2. 设置目标色数，例如 12 / 24 / 36 / 50。
3. 设置最小色块面积；默认 40 px。
4. 如需使用自己的正式色号，点击 **导入自有色库 JSON**。
5. 点击 **生成 V6 生产结果**。
6. 查看效果图与日志中的 QC 摘要。
7. 可分别导出：
   - 效果图 PNG
   - 编号线稿 SVG
   - 三页矢量 PDF
   - QC JSON

## 自有色库 JSON 格式

```json
[
  {"code": "A001", "rgb": [235, 72, 60], "name": "红"},
  {"code": "A002", "rgb": [42, 86, 190], "name": "蓝"}
]
```

程序使用 Lab 色差将分色结果匹配到正式色号。

## 运行测试

```powershell
pytest
```

## 打包 EXE

当前已经预留 PyInstaller 依赖：

```powershell
pip install -e ".[build]"
pyinstaller --noconfirm --windowed --name DigitalPaintByNumbers --paths src src/digital_paint/app.py
```

生成文件默认位于：

```text
dist/DigitalPaintByNumbers/
```

## V6 之后的重点

V6 不是最终生产版。下一阶段继续重点优化：

- 将当前拓扑安全的像素共享边界拟合为更平滑的 Bézier/矢量曲线，同时保持相邻区域共用完全同一条边。
- 更智能的小碎块判定：主体保护、边缘保留、视觉重要性和 5pt 编号容量共同评分。
- 更完整的白缝、未闭合、交叉线、尖角、锚点密度 QC。
- 自有色库编辑器与配色卡固定模板。
- 项目文件保存/恢复。
- 用户认可 AI/PDF 成品的参考样本库、错误样本库、修正记录库。
- GPU / ONNX Runtime / DirectML 加速。
- Windows 安装包和自动构建。

## 核心生产原则

效果图、线稿图、配色图必须从同一套区域数据生成；不得在三个输出阶段分别重新识别边界。共享边界只能存在一份几何定义，编号必须位于自身区域内部，自有色库正式色号必须与效果图和线稿严格对应。
