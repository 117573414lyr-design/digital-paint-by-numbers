# digital-paint-by-numbers V10

数字油画生产流水线 V10。

## V10.1 当前能力

- 指定色数分色
- 小碎块自动合并
- 5pt 编号容量规则：放不下编号的区域继续合并
- 相邻色块共享边界只输出一次，避免双线/重叠线
- 共享边界 Chaikin 平滑
- 自有色库 CSV 匹配（`number,r,g,b`）
- 编号使用自有色库编号
- 0.1pt 线稿参数
- 效果图 PNG
- 矢量线稿 SVG
- 配色 CSV
- 三页生产 PDF：效果图 / 编号线稿 / 配色卡
- QA 报告与 manifest

## 安装

```bash
python -m pip install -e .
```

## 使用

```bash
pbn-v10 input.jpg --colors 24 -o output
```

使用自有色库：

```bash
pbn-v10 input.jpg --colors 24 --color-library my-colors.csv -o output
```

色库 CSV：

```csv
number,r,g,b
A001,231,210,184
A002,88,73,63
```

## 输出

- `effect.png`
- `lineart.svg`
- `palette.csv`
- `production.pdf`
- `qa_report.json`
- `manifest.json`

## 下一阶段

1. 用 Bézier 曲线拟合替换折线式平滑
2. 邻接图驱动的智能碎块合并
3. 自有色库 Delta-E 2000 匹配与重复色控制
4. AI/PDF 三页排版模板进一步贴近成熟成品
5. 人物、风景、花卉 profile
6. Windows GUI、批处理、生产包导出
