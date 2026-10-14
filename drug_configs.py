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
                 "help": "用于利奈唑胺"},
    "age":      {"label": "年龄", "unit": "岁", "type": "number", "default": 60, "step": 1},
    "ccr":      {"label": "肌酐清除率 Ccr", "unit": "ml/min", "type": "number", "default": 90.0, "step": 1},
    "renal":    {"label": "肾功能状态", "type": "select", "options": ["无AKI且无CKD", "AKI", "CKD"],
                 "help": "万古霉素：Ccr<80 且 CRRT 时区分 AKI / CKD"},
    "crrt":     {"label": "正在 CRRT", "type": "checkbox", "default": False},
    "obese":    {"label": "肥胖患者", "type": "checkbox", "default": False,
                 "help": "万古霉素首剂 20-25mg/kg；多黏菌素 B 首剂 2-2.5mg/kg"},
    "ge80":     {"label": "体重 ≥ 80kg", "type": "checkbox", "default": False,
                 "help": "万古霉素 Ccr>120 时区分"},
    "alf":      {"label": "急性肝衰竭", "type": "checkbox", "default": False,
                 "help": "替加环素：是 → 不用"},
    "child":    {"label": "Child-Pugh 分级", "type": "select", "options": ["A", "B", "C"],
                 "help": "替加环素维持剂量分档；利奈唑胺：肝硬化 Child C → 减量"},
    "tbil":     {"label": "总胆红素 TBIL", "unit": "μmol/L", "type": "number", "default": 20.0, "step": 1,
                 "help": "利奈唑胺：TBIL>50 且 INR>2.3 → 急性肝损伤 → 减量"},
    "inr":      {"label": "INR", "unit": "", "type": "number", "default": 1.0, "step": 0.1,
                 "help": "利奈唑胺：与 TBIL 联合判断急性肝损伤"},
    "dtrpa":    {"label": "DTRPA（难治性耐药铜绿假单胞菌）", "type": "checkbox", "default": False,
                 "help": "头孢他啶/阿维巴坦：Ccr 30-50 或 CRRT 时，DTRPA → 2.5g q8h；其他 → 2.5g q12h"},
    "has_mic":  {"label": "有头孢他啶 MIC 数据", "type": "checkbox", "default": True,
                 "help": "有 MIC → 头孢他啶浓度目标 ≥4×MIC；无 MIC → 目标 8-32mg/L"},
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
    "mero_target":    {"label": "目标谷浓度", "unit": "mg/L", "type": "number", "default": 6.0, "step": 0.5,
                       "help": "目标 ≥4-8 mg/L，默认取中值 6"},
    "mero_meas":      {"label": "实测谷浓度", "unit": "mg/L", "type": "number", "default": 5.0, "step": 0.5},

    "ceftaz_meas_ca": {"label": "实测头孢他啶谷浓度", "unit": "mg/L", "type": "number", "default": 16.0, "step": 0.5},
    "ceftaz_meas_av": {"label": "实测阿维巴坦谷浓度", "unit": "mg/L", "type": "number", "default": 8.0, "step": 0.5},
    "ceftaz_neuro":   {"label": "出现神经毒性症状（抽搐、意识改变等）", "type": "checkbox", "default": False,
                       "help": "出现神经毒性 → 减为原剂量 2/3~1/2"},

    "poly_meas": {"label": "48h 实测 AUC", "unit": "mg·h/L", "type": "number", "default": 70.0, "step": 5,
                  "help": "AUC 目标 50-100 mg·h/L；抽血：谷浓度+峰浓度（用药结束后半小时，对侧静脉抽血）"},
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
    return R("前 48h 正常剂量（1g q12h）", note="AKI + CRRT：先按正常肾功能给 48h",
             detail="AKI + CRRT（Ccr<80）", level="info")


def _vanco_tdm(p):
    orig = p["vanco_orig"]
    # ① 持续泵入公式
    ci = logic.vanco_ci_adjust(p["vanco_target_ci"], p["vanco_meas_ci"], orig)
    ci_r = logic.round250(ci * 1000) / 1000.0
    r1 = R(
        f"{ci_r:.2f} g/24h 持续泵入",
        note="持续泵入公式（医生可选用）；AUC₀₋₂₄h = 随机血药浓度 × 24",
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
    """v2：六个减量条件为「或」关系，任一满足 → 300mg q12h。"""
    reasons = []
    if p["age"] > 70:
        reasons.append(f"年龄={p['age']}>70")
    if p["bw"] < 40:
        reasons.append(f"BW={p['bw']}<40kg")
    if p["ccr"] < 30:
        reasons.append(f"Ccr={p['ccr']}<30")
    if p["child"] == "C":
        reasons.append("肝硬化 Child C")
    if p["tbil"] > 50 and p["inr"] > 2.3:
        reasons.append(f"急性肝损伤（TBIL={p['tbil']}>50 且 INR={p['inr']}>2.3）")
    if p["crrt"]:
        reasons.append("CRRT")
    if reasons:
        return R("300mg q12h", note="以下条件任一满足即减量（或关系）",
                 detail=" + ".join(reasons), level="info")
    return R("600mg q12h", detail="年龄≤70，BW≥40kg，Ccr≥30，非 Child C，无急性肝损伤，非 CRRT")


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
    "inputs": ["age", "bw", "ccr", "crrt", "child", "tbil", "inr"],
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
    return R("2g（首剂）：1g 30min 泵入 + 1g 4h 泵入", note="首剂 2g 拆分为两段给药")


def _mero_maintenance(p):
    """v2：只按 Ccr 分档（>120 / 50-120 / <50），不论 AKI/CKD。"""
    ccr = p["ccr"]
    if ccr > 120:
        return R("2g q8h（2g 泵入 4h）", note="延长输注：每次泵入 4h", detail="Ccr>120")
    if ccr >= 50:
        return R("1g q8h（1g 泵入 4h）", note="延长输注：每次泵入 4h",
                 detail=f"Ccr 50-120（Ccr={ccr:.0f}，不论 AKI/CKD）")
    # Ccr<50：且关系（Ccr<50、有/无 CRRT）
    if p["crrt"]:
        return R("0.5g q6h 持续泵入", detail="Ccr<50 + 有 CRRT")
    if ccr > 25:
        return R("1g q12h", detail="Ccr<50 + 无 CRRT，25-50")
    if ccr > 10:
        return R("0.5g q12h", detail="Ccr<50 + 无 CRRT，10-25")
    return R("0.5g q24h", detail="Ccr<50 + 无 CRRT，<10")


def _mero_tdm(p):
    t = p["mero_meas"]
    target = p["mero_target"]
    orig = p["mero_orig"]
    # 精确公式（v2 PPT 原文：(目标谷浓度/2)×原每日剂量，按字面实现）
    precise = logic.mero_precise_adjust(target, t, orig)
    precise_r = logic.round250(precise * 1000) / 1000.0
    r_precise = R(
        f"{precise_r:.2f} g/24h（每次泵入 4h）",
        note="精确公式（PPT v2 原文，按字面实现，请医师核对结果）",
        detail=f"({target} / 2) × {orig} = {precise:.2f} g",
    )
    # 粗略
    if t < 4:
        r_rough = R("每日剂量加倍", detail="谷浓度 <4", level="warning")
    elif t <= 10:
        r_rough = R("不变", detail="谷浓度 4-10，达标")
    else:
        r_rough = R("每日剂量减半", detail="谷浓度 >10", level="warning")
    return [r_precise, r_rough]


MEROPENEM = {
    "name": "美罗培南",
    "ai_hint": "AI 推测患者非 CR G⁻ 杆菌可能性大",
    "continue_hint": "细菌药敏提示美罗培南敏感，继续应用",
    "inputs": ["ccr", "crrt"],
    "tdm_inputs": ["mero_orig", "mero_target", "mero_meas"],
    "tdm_target": "谷浓度目标 ≥4-8 mg/L",
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
    dtrpa = p["dtrpa"]
    if p["crrt"]:
        if dtrpa:
            return R("2.5g q8h", note="持续泵入", detail="CRRT + DTRPA（难治性耐药铜绿假单胞菌）")
        return R("2.5g q12h", note="持续泵入", detail="CRRT，非 DTRPA")
    ccr = p["ccr"]
    if ccr > 120:
        return R("2.5g q6h", note="持续泵入", detail="Ccr>120")
    if ccr >= 50:
        return R("2.5g q8h", note="持续泵入", detail="Ccr 50-120")
    if ccr >= 30:
        if dtrpa:
            return R("2.5g q8h", note="持续泵入", detail=f"Ccr 30-50（Ccr={ccr:.0f}）+ DTRPA")
        return R("2.5g q12h", note="持续泵入", detail=f"Ccr 30-50（Ccr={ccr:.0f}），非 DTRPA")
    if ccr >= 16:
        return R("1.25g q12h", note="持续泵入", detail="CKD Ccr 16-30")
    return R("1.25g qd", detail="Ccr ≤15")


def _ceftaz_tdm(p):
    has_mic = p.get("has_mic", False)
    mic = p.get("mic_ca", 0)
    tca = p["ceftaz_meas_ca"]
    tav = p["ceftaz_meas_av"]
    neuro = p.get("ceftaz_neuro", False)
    results = []
    # 毒性线（不论有无 MIC）：>40mg/L 或神经毒性 → 减量
    toxic_reasons = []
    if tca > 40:
        toxic_reasons.append(f"谷 {tca} >40 mg/L")
    if neuro:
        toxic_reasons.append("出现神经毒性症状")
    # 头孢他啶
    if has_mic and mic > 0:
        mult = tca / mic
        if toxic_reasons or mult > 10:
            reasons = toxic_reasons + ([f"谷 {tca}/MIC {mic} = {mult:.1f}×（>10×MIC）"] if mult > 10 else [])
            r = R("头孢他啶：减为原剂量 2/3~1/2", detail="；".join(reasons), level="warning")
        elif mult < 4:
            r = R("头孢他啶：考虑剂量加倍", detail=f"谷 {tca}/MIC {mic} = {mult:.1f}×（<4×MIC）", level="warning")
        else:
            r = R("头孢他啶：剂量不变", detail=f"谷 {tca}/MIC {mic} = {mult:.1f}×（4-10×MIC）")
        results.append(r)
    else:
        # 无 MIC：v2 PPT 只写明 >40 减量；不变/加倍档沿用旧版界值（32），待临床确认
        if toxic_reasons:
            r = R("头孢他啶：减为原剂量 2/3~1/2", detail="；".join(toxic_reasons), level="warning")
        elif tca < 32:
            r = R("头孢他啶：考虑剂量加倍",
                  detail=f"谷 {tca} <32 mg/L（无 MIC 档界值沿用旧版，待确认）", level="warning")
        else:
            r = R("头孢他啶：剂量不变", detail=f"谷 {tca} mg/L（32-40，无 MIC 档界值沿用旧版，待确认）")
        results.append(r)
    # 阿维巴坦：固定 ≥4mg/L；两药不一致时阿维巴坦至少要达标
    if tav < 4:
        results.append(R("阿维巴坦：不达标，需调整（两药达标不一致时，阿维巴坦至少要达标）",
                         detail=f"阿维巴坦谷 {tav} <4 mg/L", level="warning"))
    else:
        results.append(R("阿维巴坦：达标", detail=f"阿维巴坦谷 {tav} ≥4 mg/L"))
    return results


CEFTAZ = {
    "name": "头孢他啶/阿维巴坦",
    "ai_hint": "AI 推测患者非 CR G⁻ 杆菌可能性小（即 CR G⁻，KP/PA、美罗培南耐药）",
    "continue_hint": "细菌药敏提示 KP/PA、美罗培南耐药，继续应用",
    "inputs": ["ccr", "crrt", "dtrpa", "has_mic", "mic_ca", "mic_av"],
    "tdm_inputs": ["ceftaz_meas_ca", "ceftaz_meas_av", "ceftaz_neuro"],
    "tdm_target": "24h TDM，同时监测两药：头孢他啶 ≥4×MIC（有 MIC）/ 8-32mg/L（无 MIC）；"
                  "阿维巴坦 ≥4mg/L；两药达标不一致时，阿维巴坦至少要达标",
    "tdm_timing": "24h",
    "loading": _ceftaz_loading,
    "maintenance": _ceftaz_maintenance,
    "tdm_adjust": _ceftaz_tdm,
}


# ===========================================================================
# 5. 多黏菌素 B / E
# ===========================================================================

def _poly_loading(p):
    if p["obese"]:
        mg = 2.25 * p["tbw"]            # 2-2.5 中值
        return R(f"{mg:.0f}mg（首剂，肥胖 2-2.5mg/kg）",
                 note="2-2.5 取中值 2.25",
                 detail=f"2.25 × {p['tbw']} = {mg:.0f} mg")
    return R("100mg（首剂）")


def _poly_maintenance(p):
    return R("50mg q12h", detail="多黏菌素 B 固定维持剂量（v2：不区分 BMI/体重；多黏菌素 E 已移除）")


def _poly_tdm(p):
    t = p["poly_meas"]
    if t < 50:
        return [R("每次剂量 +25mg", detail="AUC <50 mg·h/L", level="warning")]
    if t <= 100:
        return [R("不变", detail="AUC 50-100 mg·h/L，达标")]
    return [R("每次剂量 −25mg", detail="AUC >100 mg·h/L", level="warning")]


POLYMYXIN = {
    "name": "多黏菌素 B",
    "ai_hint": "AI 推测患者 CR G⁻ 杆菌可能性大",
    "continue_hint": "细菌药敏提示多黏菌素敏感，继续应用",
    "inputs": ["tbw", "obese"],
    "tdm_inputs": ["poly_meas"],
    "tdm_target": "48h TDM（AUC）目标 50-100 mg·h/L；抽血：谷浓度 + 峰浓度"
                  "（用药结束后半小时，对侧静脉抽血）",
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
    return R("200mg（首剂，单次）", detail="v2：首剂统一 200mg 单次给药")


def _tige_maintenance(p):
    if p["alf"]:
        return R("不用（急性肝衰竭）", level="danger")
    if p["child"] == "C":
        return R("25-50mg q12h（区间，由临床选择）",
                 note="Child C → 25-50mg q12h 区间", level="info")
    return R("100mg q12h", detail=f"Child {p['child']}（A-B 级）→ 100mg q12h")


def _tige_tdm(p):
    # v2：替加环素取消 TDM，改为不良反应监测（见 monitoring 字段）
    return [R("不做 TDM：按不良反应监测（胃肠道反应、凝血异常、肝功能损伤、急性胰腺炎 → 建议停药）",
              level="info")]


TIGECYCLINE = {
    "name": "替加环素",
    "ai_hint": "AI 推测患者 CR G⁻ 杆菌可能性大",
    "continue_hint": "细菌药敏提示替加环素敏感，继续应用",
    "inputs": ["alf", "child"],
    "tdm_inputs": [],
    "tdm_target": "v2 起不做 TDM，以不良反应监测替代",
    "monitoring": "监测不良反应：胃肠道不良反应、凝血异常、肝功能损伤、急性胰腺炎；"
                  "以上不良反应发生建议停药",
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
