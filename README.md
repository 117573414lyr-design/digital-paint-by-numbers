# 数字油画生产软件

Windows PySide6 V0.1 已提供可运行的本地桌面程序：导入 JPG/PNG、缩放/拖动画布、选择目标色数、在后台执行 Lab/KMeans 分色、生成第一版效果图并导出 PNG。核心数据同时保存 `region_id`、`color_id` 与调色板映射，供后续线稿、配色图和矢量输出复用。

仓库中的 `docs/` 是已有 Web V110；Windows 版本位于 `app/`、`core/` 和 `tests/`，两者互不覆盖。

## Windows 安装

要求：64 位 Windows 10/11、Python 3.12。

```powershell
git clone https://github.com/117573414lyr-design/digital-paint-by-numbers.git
cd digital-paint-by-numbers
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

## 运行

```powershell
python -m app
```

也可以在安装后运行 `dpbn`。导入图片后选择色数，点击“生成效果图”；处理在线程中执行，不阻塞窗口缩放、拖动和日志刷新。

## 测试与代码检查

```powershell
python -m pip install -e .[dev]
python -m pytest
python -m ruff check .
```

无界面启动冒烟测试：

```powershell
$env:QT_QPA_PLATFORM="offscreen"
python -c "from app.main_window import MainWindow; from PySide6.QtWidgets import QApplication; app=QApplication([]); w=MainWindow(); print(w.windowTitle())"
```

## 打包 EXE

```powershell
python -m pip install -e .[dev]
pyinstaller --noconfirm --clean --windowed --name DigitalPaintByNumbers --collect-all sklearn --collect-all scipy app/main.py
```

产物位于 `dist/DigitalPaintByNumbers/`。首次打包使用目录模式，便于排查 Qt 与科学计算依赖；确认稳定后可再评估单文件模式。

## 当前边界

V0.1 已完成基础分色和 PNG 效果图；同时包含 V0.2 的第一版连通区域分析及按共享边界长度合并极小色块。0.1pt 共享边界线稿、4.2/6/8pt 编号、自有色库、可编辑矢量 PDF 和完整自动 QC 仍属于后续迭代，界面入口已明确标为未启用，避免误认为已经完成。
