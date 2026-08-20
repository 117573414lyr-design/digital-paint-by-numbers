# digital-paint-by-numbers V10

数字油画生产流水线 V10。

## 当前 V10 基线

- 图像颜色量化与指定色数分色
- 小碎块自动合并
- 每个色块连通域提取
- 区域内部距离变换放置编号
- 0.1pt 线稿参数进入配置
- 线稿 / 编号 SVG 输出
- 效果图 PNG 输出
- 配色 CSV 输出
- QA 报告与可复现 manifest

## 安装

```bash
python -m pip install -e .
```

## 使用

```bash
pbn-v10 input.jpg --colors 24 -o output
```

输出：

- `effect.png`
- `lineart.svg`
- `palette.csv`
- `qa_report.json`
- `manifest.json`

## V10 下一阶段

1. 相邻色块共享边界去重，彻底消除双线
2. Bézier 曲线拟合与锚点精简
3. 自有色库编号匹配
4. 5pt 编号容量规则与碎块二次合并
5. 线稿 PDF / 三页生产 PDF
6. 成熟 AI 样本 profile：人物 / 风景 / 花卉
7. Windows GUI、批处理与生产包导出
