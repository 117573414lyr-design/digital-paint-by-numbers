# 数字油画生产软件 V100 RC1

版本：`1.0.0rc1`

这是进入真实生产试用前的 V100 候选版。V100 的代码阶段已经汇总到可运行桌面应用，但最终 Production 标记仍需 Windows 真机与设计师 AI 成品回归验证。

## 已可使用

- Windows PySide6 桌面界面。
- 导入 PNG/JPG/JPEG/WEBP/BMP。
- 目标色数 2–256。
- 自有色库 JSON 导入。
- CIEDE2000 正式色号匹配。
- 敏感颜色防碰撞。
- 结构保护碎块优化。
- 4.2 / 6 / 8 pt 编号策略。
- 0.1 pt、CMYK 40/100/100/100 生产规范检查。
- 共享边界单线模型。
- PNG 效果图导出。
- SVG 编号线稿导出。
- 三页矢量 PDF 导出（效果/线稿/色卡）。
- QC PASS/WARN/FAIL 及问题坐标。
- 性能阶段计时。
- 内存预算与 Tile 规划。
- 磁盘缓存。
- 可取消生产任务。
- 预览滚轮缩放、拖拽平移、双击适应窗口。
- 项目编辑内核：改色、合并、拆分、移动编号、撤销/重做、快照、局部 dirty bbox。
- 手动路径修正基础与自交保护。
- 设计师参考样本的受控参数推荐接口。
- Windows PyInstaller 构建流程。
- Windows 一键安装/更新/启动脚本。

## V100 最终标记前仍需验证

1. GitHub Actions 生成的 Windows EXE 在真实 Windows 机器启动成功。
2. 12MP / 24MP / 48MP 在目标电脑上的实际耗时与内存数据。
3. 用户设计师成熟 AI 文件作为真实视觉回归样本逐项验收。
4. 矢量 PDF 在 Illustrator 中检查：路径/文字可编辑、颜色完整、无漏白。
5. 自有正式色库全量导入与色号核对。
6. 长时间连续生产稳定性。
7. Windows SmartScreen / 杀毒软件误报情况记录。

## 推荐试用顺序

1. 先用 12–24 色的小图验证效果、编号和导出。
2. 再导入自有色库测试 CIEDE2000 匹配。
3. 导出 PDF 到 Illustrator，检查线宽、文字、色块和共享边界。
4. 再测试 36–50 色和大图。
5. 将用户确认“正确”的结果记录为 reference sample；错误结果记录为 negative/correction sample。

## 安装方式

优先使用 GitHub Actions 生成的 `DigitalPaintByNumbers-Windows` EXE/文件夹包。

如果 EXE 尚未取到，可运行仓库根目录的 `Install-V100-RC1.bat`。该脚本会建立独立 Python 3.12 环境、安装当前分支并启动 `digital-paint`。
