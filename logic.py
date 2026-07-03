"""logic.py — 通用计算函数：体重指标、剂量取整、TDM 调整公式。

所有函数纯函数、无副作用，便于在 drug_configs / app 中复用与单测。
"""

from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# 体重相关指标
# ---------------------------------------------------------------------------

def ibw(height_cm: float, sex: str) -> float:
    """理想体重 (Ideal Body Weight, kg)。

    男性: IBW = 50 + 0.91 × (身高cm − 152.4)
    女性: IBW = 45.5 + 0.91 × (身高cm − 152.4)
    """
    h = float(height_cm)
    base = 50.0 if sex == "男" else 45.5
    return base + 0.91 * (h - 152.4)


def adjbw(tbw: float, ibw_val: float) -> float:
    """校正体重 (Adjusted Body Weight, kg) = IBW + 0.4 × (TBW − IBW)。"""
    return float(ibw_val) + 0.4 * (float(tbw) - float(ibw_val))


def bmi(tbw: float, height_cm: float) -> float:
    """BMI = 体重kg / 身高m^2。"""
    h = float(height_cm) / 100.0
    if h <= 0:
        return 0.0
    return float(tbw) / (h * h)


# ---------------------------------------------------------------------------
# 剂量取整
# ---------------------------------------------------------------------------

ABX_PER_DOSE_STEPS = [500, 750, 1000]      # mg，抗生素单次剂量取整档位
POLYMYXIN_STEPS_MG = [50, 100, 150]        # 多黏菌素单次剂量档位（1 万 u = 1 mg）


def round_to_nearest(value: float, steps: List[float]) -> float:
    """把 value 取到 steps 中最接近的一档。"""
    return min(steps, key=lambda s: abs(s - value))


def round250(mg: float) -> float:
    """取整到最近的 250mg（500/750/1000 均在 250 网格上）。

    用于首剂量等可能 >1000mg 的单次剂量。
    """
    return round(float(mg) / 250.0) * 250.0


# 常见给药频次：(每日次数, 文字)
_FREQS: List[Tuple[float, str]] = [
    (4.0, "q6h"),
    (3.0, "q8h"),
    (2.0, "q12h"),
    (1.0, "q24h"),
    (0.5, "q48h"),
]


def round_daily_to_regimen(total_mg: float, steps: List[float] = ABX_PER_DOSE_STEPS) -> dict:
    """把每日总剂量 (mg) 拆成「单次剂量 × 频次」，单次剂量落在 steps 上。

    返回 {"per_dose": mg, "freq": "qXh", "daily": mg, "text": "750mg q12h"}。
    选择使实际每日总量最接近目标的组合。
    """
    total = float(total_mg)
    best = None
    for times, label in _FREQS:
        per = round_to_nearest(total / times, steps)
        actual = per * times
        err = abs(actual - total)
        if best is None or err < best[0]:
            best = (err, per, label, actual)
    err, per, label, actual = best
    mg = int(per)
    return {
        "per_dose": mg,
        "freq": label,
        "daily": actual,
        "text": _fmt_dose(mg, label),
    }


def _fmt_dose(mg: float, freq: str) -> str:
    """把 mg 格式化为 g/mg 文本。"""
    if mg >= 1000 and mg % 1000 == 0:
        return f"{int(mg)//1000}g {freq}"
    return f"{int(mg)}mg {freq}"


# ---------------------------------------------------------------------------
# TDM 调整公式
# ---------------------------------------------------------------------------

def vanco_ci_adjust(target_conc: float, measured_conc: float, original_daily_g: float) -> float:
    """万古霉素 持续泵入 公式：新日剂量 = (目标随机浓度 / 实测随机浓度) × 原日剂量。

    返回新每日剂量 (g)。
    """
    if measured_conc <= 0:
        return original_daily_g
    return (float(target_conc) / float(measured_conc)) * float(original_daily_g)


def vanco_auc_adjust(target_auc: float, measured_auc: float, original_daily_g: float) -> float:
    """万古霉素 AUC 公式：新日剂量 = (目标 AUC / 实测 AUC) × 原日剂量。"""
    if measured_auc <= 0:
        return original_daily_g
    return (float(target_auc) / float(measured_auc)) * float(original_daily_g)


def mero_precise_adjust(target_trough: float, measured_trough: float, original_daily_g: float) -> float:
    """美罗培南 精确 公式。

    PPT 原文为 (目标谷浓度 / 2) × 原每日剂量，但维度异常（疑为
    (目标谷浓度 / 实测谷浓度) 之笔误）。此处按临床常规实现：
        新日剂量 = (目标谷浓度 / 实测谷浓度) × 原日剂量
    app 中会显著标注此差异，请临床确认。
    """
    if measured_trough <= 0:
        return original_daily_g
    return (float(target_trough) / float(measured_trough)) * float(original_daily_g)
