# 抗生素剂量与 TDM 调整计算器

将 `version2 医科院高水平项目抗生素剂量及TDM调整流程.pptx` 的 6 种抗生素「首剂 + 维持 + TDM 调整」流程实现为交互式 Streamlit 计算器。

## 快速开始

```bash
pip install -r requirements.txt
streamlit run app.py
```

浏览器打开后：
1. 左侧栏选择抗生素（6 选 1）
2. 主区域填入患者参数（体重 / Ccr / 肾状态 / CRRT / 身高 / Child 分级 / MIC 等，按药物动态显示）
3. 勾选「用药指征确认」
4. 查看「首剂量 / 维持剂量」
5. 48h 后在右侧「TDM 调整」填入实测浓度 → 点「计算 TDM 调整」
6. 调整后 48h 再次 TDM，循环至达标

## 文件结构

| 文件 | 作用 |
|---|---|
| `app.py` | Streamlit 主程序（侧边栏选药 + 动态输参 + 结果/TDM 面板） |
| `drug_configs.py` | 6 种药的规则（首剂 / 维持 / TDM 函数 + 输入字段定义），数据驱动 |
| `logic.py` | 通用计算：IBW / AdjBW / BMI、剂量取整、TDM 公式 |
| `requirements.txt` | 依赖（streamlit） |

## 覆盖的 6 种药

| 药物 | AI 推测病原 | 核心决策变量 |
|---|---|---|
| 经验性万古霉素 | MRSA 可能性大 | 体重、Ccr、AKI/CKD、CRRT |
| 经验性利奈唑胺 | MRSA 可能性大 | Ccr、年龄、体重 |
| 美罗培南 | 非 CR G⁻ 杆菌 | Ccr、AKI/CKD、CRRT |
| 头孢他啶/阿维巴坦 | 非 CR G⁻ 杆菌可能性小 | Ccr、CRRT、MIC |
| 多黏菌素 B / E | CR G⁻ 杆菌 | BMI、AdjBW/IBW |
| 替加环素 | CR G⁻ 杆菌 | 急性肝衰竭、Child 分级、体重 |

## 已知留白 / 待临床确认（重要）

实现时尽量忠实于 PPT 原文，但下列点存在歧义，已在 UI 显著标注，**最终方案须由医师判定**：

1. **美罗培南精确公式**：PPT 原文为 `(目标谷浓度 / 2) × 原每日剂量`，维度异常（疑为 `(目标 / 实测)` 笔误）。本工具按临床常规 `(目标谷浓度 / 实测谷浓度) × 原每日剂量` 实现，并在结果旁标注差异，请临床确认。粗略调整（加倍 / 不变 / 减半）不受影响。

2. **多黏菌素 TDM 单位**：目标写作 `50-100 mg/L`，调整栏写作 `mg·h/L`，单位不一致。本工具按数值阈值 `50 / 100` 处理。

3. **替加环素「？？？」阈值**：PPT 未定值。本工具做成可输入字段（带「启用」开关），默认占位值 1.2，请按临床设定；未启用时只保留「<0.9 加倍 / ≥0.9 不变」两条分支。

4. **替加环素维持剂量**：Child 分级与 `BW≥100kg` 两条线并存。本工具实现为：`BW≥100kg` 时覆盖为 `100mg q12h`，否则按 Child 分级（A-B→50mg q12h，C→25mg q12h）。

5. **利奈唑胺 Ccr≤30 但未达减量条件**（非「年龄>70 且 BW<40」）：PPT 未覆盖，默认按 `600mg q12h` 并提示。

6. **万古霉素 TDM 两套公式**（持续泵入 / AUC）均计算并并列展示，由医生选用。

## 修改/扩展

- 新增/调整某药规则：编辑 `drug_configs.py` 中对应配置块（`inputs` / `loading` / `maintenance` / `tdm_adjust`），UI 自动适配。
- 新增输入字段：在 `drug_configs.py` 的 `INPUTS` 字典加一项，再到对应药物的 `inputs`/`tdm_inputs` 引用其 key。

#日常使用
应用已在后台运行，浏览器打开 http://localhost:8501 即可。若需重启：
cd "/Users/liushuangfei/Research/医科院抗生素"
python3 -m streamlit run app.py
要调整任何药物的规则或新增药物，只需改 drug_configs.py 对应块，UI 自动适配。