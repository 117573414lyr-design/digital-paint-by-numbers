# digital-paint-by-numbers

Windows 本地数字油画生产软件。

当前开发分支：`feature/windows-v0.1`

## V0.1 已实现

- PySide6 Windows 桌面界面
- JPG / PNG / JPEG / WEBP 图片导入
- 原图预览与自适应缩放
- 2–256 自定义目标色数，默认 24 色
- RGB → CIE Lab
- KMeans 基础分色
- 数字油画效果图预览
- PNG 导出
- 后台线程处理，避免阻塞 GUI
- 运行日志与异常提示
- `color_id` / `region_id` 数据接口
- 最小核心单元测试

> V0.1 是生产软件的第一层基础。线稿、碎块合并、共享边界、自有色库、编号、矢量 PDF 和自动质检将在后续版本继续实现，具体生产标准以仓库根目录 `AGENTS.md` 为准。

## Windows 安装

建议 Windows 10/11 + Python 3.12 64-bit。

```powershell
git clone https://github.com/117573414lyr-design/digital-paint-by-numbers.git
cd digital-paint-by-numbers
git checkout feature/windows-v0.1
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## 启动软件

```powershell
digital-paint
```

也可以：

```powershell
python -m digital_paint.app
```

## V0.1 使用方法

1. 点击“导入 JPG / PNG”。
2. 选择目标色数，例如 12、24、36、50 色。
3. 点击“生成数字油画效果图”。
4. 查看右侧效果图。
5. 点击“导出 PNG”保存当前分色结果。

## 运行测试

```powershell
pytest
```

## 后续路线

### V0.2 区域化与碎块处理

- 连通区域分析，生成稳定 `region_id`
- 小碎块检测和生产级合并
- 相邻关系图
- 平滑边界
- 防白缝/透明缝

### V0.3 线稿生产

- 相邻色块共享边界
- 单一边线，禁止双线/重线/交叉线
- 0.1 pt 生产线宽
- CMYK 40,100,100,100
- 平滑闭合矢量曲线

### V0.4 编号与自有色库

- 用户自有色库匹配
- 色号映射
- 4.2 / 6 / 8 pt 自动编号
- 编号越界检测
- 放不下生产编号的无意义小色块继续合并

### V0.5 矢量 PDF 与生产 QC

- 效果图 / 编号线稿 / 配色图一致性
- 可编辑矢量路径
- PDF 输出
- 白缝、漏色、未闭合、重复线、错号、色块不一致自动质检

## 项目原则

效果图、线稿图、配色图必须基于同一套区域与颜色数据生成，确保区域、边界、编号和色号一一对应。不得为方便编号或线稿而机械粗暴简化图像。
