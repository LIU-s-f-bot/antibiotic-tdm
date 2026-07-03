"""drug_configs.py — 6 种抗生素的剂量与 TDM 规则（配置驱动）。

每种药声明：
  - 元信息 (name / ai_hint / continue_hint)
  - inputs        : 基础参数输入 key 列表（渲染到「患者参数」区）
  - tdm_inputs    : TDM 面板输入 key 列表
  - tdm_target    : TDM 目标文字（展示用）
  - loading(p)    : 返回首剂量结果 dict
  - maintenance(p): 返回维持剂量结果 dict
  - tdm_adjust(p) : 返回 TDM 调整结果列表（万古霉素会有 2 条）

结果 dict 结构：
  {"dose": str, "note": str, "detail": str, "level": "normal"|"info"|"warning"|"danger"}
"""

import logic


# ---------------------------------------------------------------------------
# 结果构造助手
# ---------------------------------------------------------------------------

def R(dose, note="", detail="", level="normal"):
    return {"dose": dose, "note": note, "detail": detail, "level": level}


def _fmt(mg: float) -> str:
    """mg → '2g' / '750mg' 文本。"""
    if mg >= 1000 and abs(mg - round(mg / 1000) * 1000) < 1e-6:
        return f"{int(round(mg / 1000))}g"
    return f"{int(round(mg))}mg"


# ---------------------------------------------------------------------------
# 输入字段定义（key -> 渲染元信息）
# ---------------------------------------------------------------------------

INPUTS = {
    # —— 基础参数 ——
    "tbw":      {"label": "实际体重 TBW", "unit": "kg", "type": "number", "default": 70.0, "step": 0.5,
                 "help": "实际（总体）体重"},
    "bw":       {"label": "体重 BW", "unit": "kg", "type": "number", "default": 70.0, "step": 0.5,
                 "help": "用于利奈唑胺 / 替加环素"},
    "height":   {"label": "身高", "unit": "cm", "type": "number", "default": 170.0, "step": 0.5},
    "sex":      {"label": "性别", "type": "select", "options": ["男", "女"]},
    "age":      {"label": "年龄", "unit": "岁", "type": "number", "default": 60, "step": 1},
    "ccr":      {"label": "肌酐清除率 Ccr", "unit": "ml/min", "type": "number", "default": 90.0, "step": 1},
    "renal":    {"label": "肾功能状态", "type": "select", "options": ["无AKI且无CKD", "AKI", "CKD"],
                 "help": "万古霉素/美罗培南：Ccr<80 且 CRRT 时区分 AKI / CKD"},
    "crrt":     {"label": "正在 CRRT", "type": "checkbox", "default": False},
    "obese":    {"label": "肥胖患者", "type": "checkbox", "default": False,
                 "help": "万古霉素首剂按 20-25mg/kg"},
    "ge80":     {"label": "体重 ≥ 80kg", "type": "checkbox", "default": False,
                 "help": "万古霉素 Ccr>120 时区分"},
    "which_poly": {"label": "多黏菌素种类", "type": "select", "options": ["多黏菌素 B", "多黏菌素 E"],
                   "help": "B 用 AdjBW；E 用 IBW"},
    "alf":      {"label": "急性肝衰竭", "type": "checkbox", "default": False,
                 "help": "替加环素：是 → 不用"},
    "child":    {"label": "Child-Pugh 分级", "type": "select", "options": ["A", "B", "C"]},
    "mic_ca":   {"label": "头孢他啶 MIC", "unit": "mg/L", "type": "number", "default": 4.0, "step": 0.5},
    "mic_av":   {"label": "阿维巴坦 MIC", "unit": "mg/L", "type": "number", "default": 4.0, "step": 0.5,
                 "help": "阿维巴坦目标固定 ≥4mg/L，此处 MIC 仅供参考记录"},

    # —— TDM 参数 ——
    "vanco_orig":      {"label": "原每日剂量", "unit": "g/24h", "type": "number", "default": 2.0, "step": 0.25},
    "vanco_target_ci": {"label": "目标随机浓度", "unit": "mg/L", "type": "number", "default": 20.0, "step": 1,
                        "help": "持续泵入目标 15-25mg/L，默认取中值 20"},
    "vanco_meas_ci":   {"label": "实测随机浓度", "unit": "mg/L", "type": "number", "default": 10.0, "step": 0.5},
    "vanco_target_auc":{"label": "目标 AUC", "unit": "", "type": "number", "default": 500.0, "step": 10,
                        "help": "目标 AUC 400-600，默认取中值 500"},
    "vanco_meas_auc":  {"label": "实测 AUC", "unit": "", "type": "number", "default": 400.0, "step": 10},

    "lin_meas":  {"label": "实测谷浓度", "unit": "mg/L", "type": "number", "default": 5.0, "step": 0.5},
    "lin_plt":   {"label": "血小板 PLT", "unit": "×10⁹/L", "type": "number", "default": 150.0, "step": 10,
                  "help": "原阈值 PLT<5 万/μL ≈ 50×10⁹/L"},

    "mero_orig":      {"label": "原每日剂量", "unit": "g/24h", "type": "number", "default": 6.0, "step": 0.5},
    "mero_target":    {"label": "目标谷浓度", "unit": "mg/L", "type": "number", "default": 14.0, "step": 1,
                       "help": "目标 8-20mg/L，默认取中值 14"},
    "mero_meas":      {"label": "实测谷浓度", "unit": "mg/L", "type": "number", "default": 12.0, "step": 0.5},

    "ceftaz_meas_ca": {"label": "实测头孢他啶谷浓度", "unit": "mg/L", "type": "number", "default": 16.0, "step": 0.5},
    "ceftaz_meas_av": {"label": "实测阿维巴坦谷浓度", "unit": "mg/L", "type": "number", "default": 8.0, "step": 0.5},

    "poly_meas": {"label": "实测谷浓度", "unit": "mg/L", "type": "number", "default": 70.0, "step": 5,
                  "help": "目标 50-100mg/L（原文调整栏单位写作 mg·h/L，按数值阈值处理）"},

    "tige_meas":   {"label": "实测 fAUC/MIC", "unit": "", "type": "number", "default": 0.9, "step": 0.05},
    "tige_thresh": {"label": "「减半」阈值（？？？）", "unit": "", "type": "number", "default": 1.2, "step": 0.1,
                    "toggle": "启用「减半」阈值",
                    "help": "PPT 未定值。取消勾选则不启用「减半」分支；默认值 1.2 仅为占位，请按临床设定"},
}


# ===========================================================================
# 1. 万古霉素
# ===========================================================================

def _vanco_loading(p):
    tbw = p["tbw"]
    if p["obese"]:
        mg = 22.5 * tbw          # 20-25 中值
        raw = f"22.5 × {tbw} = {mg:.0f} mg/kg（肥胖 20-25）"
    else:
        mg = 27.5 * tbw          # 20-35 中值
        raw = f"27.5 × {tbw} = {mg:.0f} mg/kg（20-35）"
    mg = min(mg, 3000)            # Max < 3g
    rounded = logic.round250(mg)
    return R(
        f"{_fmt(rounded)}（首剂）",
        note="Max < 3g，取整到 250mg",
        detail=f"{raw}  →  封顶 3000  →  取整 {_fmt(rounded)}",
    )


def _vanco_maintenance(p):
    ccr = p["ccr"]
    crrt = p["crrt"]
    renal = p["renal"]
    if ccr > 120:
        if p["ge80"]:
            return R("1g q6h", note="CVC；24h 持续泵入", detail="Ccr>120 且 ≥80kg")
        return R("1g q8h", note="CVC；24h 持续泵入", detail="Ccr>120 且 <80kg")
    if ccr >= 80:                 # 80-120
        return R("1g q12h", note="24h 持续泵入", detail="Ccr 80-120")
    # Ccr < 80
    if not crrt:
        if ccr > 50:
            return R("750mg q12h", detail="Ccr<80 无 CRRT，50-80")
        if ccr > 30:
            return R("500mg q12h", detail="Ccr<80 无 CRRT，30-50")
        if ccr > 20:
            return R("500mg q24h", detail="Ccr<80 无 CRRT，20-30")
        return R("500mg q48h", detail="Ccr<80 无 CRRT，<20")
    # Ccr<80 且 CRRT
    if renal == "CKD":
        return R("500mg q12h", note="持续泵入", detail="CKD + CRRT")
    return R("前 48h 正常剂量", note="AKI + CRRT：先按正常肾功能给 48h",
             detail="AKI + CRRT（Ccr<80）", level="info")


def _vanco_tdm(p):
    orig = p["vanco_orig"]
    # ① 持续泵入公式
    ci = logic.vanco_ci_adjust(p["vanco_target_ci"], p["vanco_meas_ci"], orig)
    ci_r = logic.round250(ci * 1000) / 1000.0
    r1 = R(
        f"{ci_r:.2f} g/24h 持续泵入",
        note="持续泵入公式（医生可选用）",
        detail=f"({p['vanco_target_ci']} / {p['vanco_meas_ci']}) × {orig} = {ci:.2f} g",
    )
    # ② AUC 公式
    auc = logic.vanco_auc_adjust(p["vanco_target_auc"], p["vanco_meas_auc"], orig)
    auc_r = logic.round250(auc * 1000) / 1000.0
    r2 = R(
        f"{auc_r:.2f} g/24h",
        note="AUC 公式（医生可选用）",
        detail=f"({p['vanco_target_auc']} / {p['vanco_meas_auc']}) × {orig} = {auc:.2f} g",
    )
    return [r1, r2]


VANCO = {
    "name": "经验性万古霉素",
    "ai_hint": "AI 推测患者 MRSA 可能性大",
    "continue_hint": "细菌及药敏提示有万古霉素使用指征，继续应用",
    "inputs": ["tbw", "obese", "ccr", "renal", "crrt", "ge80"],
    "tdm_inputs": ["vanco_orig", "vanco_target_ci", "vanco_meas_ci", "vanco_target_auc", "vanco_meas_auc"],
    "tdm_target": "谷浓度 10~20 mg/L；持续泵入 15-25mg/L，AUC 400-600",
    "loading": _vanco_loading,
    "maintenance": _vanco_maintenance,
    "tdm_adjust": _vanco_tdm,
}


# ===========================================================================
# 2. 利奈唑胺
# ===========================================================================

def _lin_loading(p):
    return R("600mg（首剂）")


def _lin_maintenance(p):
    ccr = p["ccr"]
    if ccr > 30 or p["crrt"]:
        return R("600mg q12h", detail="Ccr>30 或 CRRT")
    # Ccr <= 30
    if p["age"] > 70 and p["bw"] < 40:
        return R("300mg q12h", detail="年龄>70 且 BW<40kg 且 Ccr<30", level="info")
    return R("600mg q12h", note="Ccr≤30 但未达减量条件，按常规（PPT 未覆盖该组合）", level="info")


def _lin_tdm(p):
    t = p["lin_meas"]
    plt = p["lin_plt"]
    if t < 2:
        return [R("加倍：300mg q12h→600mg q12h；600mg q12h→600mg q8h",
                  detail="谷浓度 <2，每日剂量加倍", level="warning")]
    if t <= 7:
        return [R("不变", detail="谷浓度 2-7，达标")]
    if t <= 10:
        return [R("每日剂量减半", detail="谷浓度 7-10", level="warning")]
    # > 10
    if plt is not None and plt < 50:
        return [R("暂停给药", detail=f"谷浓度 >10 且 PLT={plt}<50×10⁹/L", level="danger")]
    return [R("每日剂量减半", detail=f"谷浓度 >10（PLT={plt}≥50）", level="warning")]


LINEZOLID = {
    "name": "经验性利奈唑胺",
    "ai_hint": "AI 推测患者 MRSA 可能性大",
    "continue_hint": "细菌及药敏提示有利奈唑胺使用指征，继续应用",
    "inputs": ["age", "bw", "ccr", "crrt"],
    "tdm_inputs": ["lin_meas", "lin_plt"],
    "tdm_target": "谷浓度 2-7 mg/L",
    "loading": _lin_loading,
    "maintenance": _lin_maintenance,
    "tdm_adjust": _lin_tdm,
}


# ===========================================================================
# 3. 美罗培南
# ===========================================================================

def _mero_loading(p):
    return R("2g（首剂）")


def _mero_maintenance(p):
    ccr = p["ccr"]
    renal = p["renal"]
    if ccr > 120:
        return R("2g q8h", note="持续泵入", detail="Ccr>120")
    if ccr >= 80:
        return R("1g q8h", note="持续泵入", detail="Ccr 80-120")
    # Ccr < 80
    if renal == "AKI":
        return R("前 48h 正常剂量", note="AKI（Ccr<80）：先按正常肾功能给 48h",
                 detail="AKI + Ccr<80", level="info")
    # CKD
    if p["crrt"]:
        return R("1g q12h", note="持续泵入", detail="CKD + CRRT")
    if ccr > 25:
        return R("1g q12h", detail="CKD 无 CRRT，25-50")
    if ccr > 10:
        return R("0.5g q12h", detail="CKD 无 CRRT，10-25")
    return R("0.5g q24h", detail="CKD 无 CRRT，<10")


def _mero_tdm(p):
    t = p["mero_meas"]
    target = p["mero_target"]
    orig = p["mero_orig"]
    # 精确公式（按目标/实测实现，PPT 原文为 /2）
    precise = logic.mero_precise_adjust(target, t, orig)
    precise_r = logic.round250(precise * 1000) / 1000.0
    r_precise = R(
        f"{precise_r:.2f} g/24h 持续泵入",
        note="⚠️ 精确公式：PPT 原文 (目标谷浓度/2)×原剂量 疑为笔误，此处按 (目标/实测)×原剂量 实现，请临床确认",
        detail=f"({target} / {t}) × {orig} = {precise:.2f} g",
        level="warning",
    )
    # 粗略
    if t < 8:
        r_rough = R("每日剂量加倍", detail="谷浓度 <8", level="warning")
    elif t <= 20:
        r_rough = R("不变", detail="谷浓度 8-20，达标")
    elif t <= 50:
        r_rough = R("每日剂量减半", detail="谷浓度 20-50", level="warning")
    else:
        r_rough = R("每日剂量减半", detail="谷浓度 >50，明显超标", level="danger")
    return [r_precise, r_rough]


MEROPENEM = {
    "name": "美罗培南",
    "ai_hint": "AI 推测患者非 CR G⁻ 杆菌可能性大",
    "continue_hint": "细菌药敏提示美罗培南敏感，继续应用",
    "inputs": ["ccr", "renal", "crrt"],
    "tdm_inputs": ["mero_orig", "mero_target", "mero_meas"],
    "tdm_target": "谷浓度 8-20 mg/L",
    "loading": _mero_loading,
    "maintenance": _mero_maintenance,
    "tdm_adjust": _mero_tdm,
}


# ===========================================================================
# 4. 头孢他啶/阿维巴坦
# ===========================================================================

def _ceftaz_loading(p):
    if p["crrt"]:
        return R("2.5g（首剂）", detail="CRRT 时给首剂")
    return R("无需首剂", detail="非 CRRT 情况无需首剂", level="info")


def _ceftaz_maintenance(p):
    if p["crrt"]:
        return R("2.5g q12h", note="持续泵入", detail="CRRT")
    ccr = p["ccr"]
    if ccr > 120:
        return R("2.5g q6h", note="持续泵入", detail="Ccr>120")
    if ccr >= 50:
        return R("2.5g q8h", note="持续泵入", detail="Ccr 50-120")
    if ccr >= 30:
        return R("2.5g q12h", note="持续泵入", detail="Ccr 30-50")
    if ccr >= 16:
        return R("1.25g q12h", note="持续泵入", detail="CKD Ccr 16-30")
    return R("1.25g qd", detail="Ccr ≤15")


def _ceftaz_tdm(p):
    mic = p["mic_ca"]
    tca = p["ceftaz_meas_ca"]
    tav = p["ceftaz_meas_av"]
    results = []
    # 头孢他啶：按 MIC 倍数
    if mic > 0:
        mult = tca / mic
        if mult < 4:
            r = R("头孢他啶：剂量加倍", detail=f"谷 {tca} / MIC {mic} = {mult:.1f}× (<4×MIC)", level="warning")
        elif mult <= 10:
            r = R("头孢他啶：剂量不变", detail=f"谷 {tca} / MIC {mic} = {mult:.1f}× (4-10×MIC)")
        else:
            r = R("头孢他啶：减为原剂量 2/3~1/2",
                  detail=f"谷 {tca} / MIC {mic} = {mult:.1f}× (>10×MIC) 或出现神经毒性", level="warning")
        results.append(r)
    # 阿维巴坦：固定 ≥4mg/L
    if tav < 4:
        results.append(R("阿维巴坦：剂量加倍", detail=f"阿维巴坦谷 {tav} <4 mg/L", level="warning"))
    else:
        results.append(R("阿维巴坦：达标", detail=f"阿维巴坦谷 {tav} ≥4 mg/L"))
    return results


CEFTAZ = {
    "name": "头孢他啶/阿维巴坦",
    "ai_hint": "AI 推测患者非 CR G⁻ 杆菌可能性小（即 CR G⁻，KP/PA、美罗培南耐药）",
    "continue_hint": "细菌药敏提示 KP/PA、美罗培南耐药，继续应用",
    "inputs": ["ccr", "crrt", "mic_ca", "mic_av"],
    "tdm_inputs": ["ceftaz_meas_ca", "ceftaz_meas_av"],
    "tdm_target": "必须同时监测：头孢他啶谷 ≥4×MIC（无 MIC 时 ≥8mg/L）；阿维巴坦谷 ≥4mg/L",
    "loading": _ceftaz_loading,
    "maintenance": _ceftaz_maintenance,
    "tdm_adjust": _ceftaz_tdm,
}


# ===========================================================================
# 5. 多黏菌素 B / E
# ===========================================================================

def _poly_loading(p):
    tbw = p["tbw"]
    h = p["height"]
    bmi_val = logic.bmi(tbw, h)
    if bmi_val >= 28:
        mg = 2.25 * tbw            # 2-2.5 中值
        per = logic.round_to_nearest(mg, logic.POLYMYXIN_STEPS_MG)
        return R(f"{_fmt(per)}（首剂，肥胖）",
                 note="1 万 u = 1 mg；取整到 50/100/150",
                 detail=f"肥胖 2.25 × {tbw} = {mg:.0f} mg → 取整 {_fmt(per)}")
    return R("100mg（首剂）")


def _poly_maintenance(p):
    tbw = p["tbw"]
    h = p["height"]
    bmi_val = logic.bmi(tbw, h)
    if bmi_val < 28:
        return R("50mg q12h", detail=f"BMI={bmi_val:.1f} <28")
    ibw_val = logic.ibw(h, p["sex"])
    if p["which_poly"] == "多黏菌素 B":
        w = logic.adjbw(tbw, ibw_val)
        wt_txt = f"AdjBW = IBW({ibw_val:.1f}) + 0.4×(TBW({tbw})−IBW) = {w:.1f}"
    else:
        w = ibw_val
        wt_txt = f"IBW = {ibw_val:.1f}（多黏菌素 E 用 IBW）"
    mg = 1.375 * w                  # 1.25-1.5 中值
    per = logic.round_to_nearest(mg, logic.POLYMYXIN_STEPS_MG)
    return R(f"{_fmt(per)} q12h", note="1 万 u = 1 mg；取整到 50/100/150",
             detail=f"BMI={bmi_val:.1f} ≥28；{wt_txt}；1.375×{w:.1f}={mg:.0f} → 取整 {_fmt(per)}")


def _poly_tdm(p):
    t = p["poly_meas"]
    if t < 50:
        return [R("每次剂量 +25mg", detail="谷浓度 <50", level="warning")]
    if t <= 100:
        return [R("不变", detail="谷浓度 50-100，达标")]
    return [R("每次剂量 −25mg", detail="谷浓度 >100", level="warning")]


POLYMYXIN = {
    "name": "多黏菌素 B / E",
    "ai_hint": "AI 推测患者 CR G⁻ 杆菌可能性大",
    "continue_hint": "细菌药敏提示多黏菌素敏感，继续应用",
    "inputs": ["tbw", "height", "sex", "which_poly"],
    "tdm_inputs": ["poly_meas"],
    "tdm_target": "谷浓度 50-100 mg/L",
    "loading": _poly_loading,
    "maintenance": _poly_maintenance,
    "tdm_adjust": _poly_tdm,
}


# ===========================================================================
# 6. 替加环素
# ===========================================================================

def _tige_loading(p):
    if p["alf"]:
        return R("不用（急性肝衰竭）", level="danger")
    bw = p["bw"]
    if bw < 100:
        return R("100mg（首剂）", detail="BW<100kg")
    return R("150mg（首剂）", detail="BW≥100kg")


def _tige_maintenance(p):
    if p["alf"]:
        return R("不用（急性肝衰竭）", level="danger")
    bw = p["bw"]
    child = p["child"]
    if bw >= 100:
        return R("100mg q12h", detail="BW≥100kg（覆盖常规 Child 分级方案）", level="info")
    if child in ("A", "B"):
        return R("50mg q12h", detail="Child-Pugh A-B")
    return R("25mg q12h", detail="Child-Pugh C", level="info")


def _tige_tdm(p):
    fr = p["tige_meas"]
    thresh = p["tige_thresh"]
    if fr < 0.9:
        return [R("剂量加倍", detail=f"fAUC/MIC = {fr} <0.9", level="warning")]
    if thresh not in (None, 0) and fr >= thresh:
        return [R("剂量减半", detail=f"fAUC/MIC = {fr} ≥ 阈值 {thresh}", level="warning")]
    return [R("不变", detail=f"fAUC/MIC = {fr} ≥0.9，达标")]


TIGECYCLINE = {
    "name": "替加环素",
    "ai_hint": "AI 推测患者 CR G⁻ 杆菌可能性大",
    "continue_hint": "细菌药敏提示替加环素敏感，继续应用",
    "inputs": ["alf", "child", "bw"],
    "tdm_inputs": ["tige_meas", "tige_thresh"],
    "tdm_target": "fAUC/MIC ≥ 0.9",
    "loading": _tige_loading,
    "maintenance": _tige_maintenance,
    "tdm_adjust": _tige_tdm,
}


# ===========================================================================
# 注册表
# ===========================================================================

DRUGS = {
    "vancomycin": VANCO,
    "linezolid":  LINEZOLID,
    "meropenem":  MEROPENEM,
    "ceftaz":     CEFTAZ,
    "polymyxin":  POLYMYXIN,
    "tigecycline": TIGECYCLINE,
}
