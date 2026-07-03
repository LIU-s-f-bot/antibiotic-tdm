"""app.py — 医科院抗生素剂量与 TDM 调整计算器（Streamlit）。

用法：
    streamlit run app.py
"""

import streamlit as st

import drug_configs as dc


# ---------------------------------------------------------------------------
# 输入控件渲染
# ---------------------------------------------------------------------------

def render_input(key, container):
    """根据 INPUTS[key] 渲染一个控件，返回其值。"""
    spec = dc.INPUTS[key]
    label = spec["label"]
    unit = spec.get("unit", "")
    full_label = f"{label}" + (f"（{unit}）" if unit else "")
    help_txt = spec.get("help")
    t = spec["type"]

    # 可选字段：先用 toggle 决定是否启用
    enabled = True
    if "toggle" in spec:
        enabled = container.checkbox(spec["toggle"], value=False, help=help_txt)
        if not enabled:
            return None
        help_txt = None  # help 已在 toggle 上显示

    if t == "number":
        return float(container.number_input(
            full_label, value=float(spec["default"]),
            step=float(spec.get("step", 1.0)), help=help_txt))
    if t == "select":
        return container.selectbox(full_label, spec["options"], help=help_txt)
    if t == "checkbox":
        return container.checkbox(full_label, value=bool(spec["default"]), help=help_txt)
    raise ValueError(f"未知控件类型: {t}")


# ---------------------------------------------------------------------------
# 结果展示
# ---------------------------------------------------------------------------

_LEVEL_STYLE = {
    "normal":  ("✅", "info"),
    "info":    ("ℹ️", "info"),
    "warning": ("⚠️", "warning"),
    "danger":  ("🚫", "error"),
}


def show_result(container, title, res):
    """展示单个结果（首剂 / 维持 / 一条 TDM 调整）。"""
    icon, banner = _LEVEL_STYLE.get(res.get("level", "normal"), ("✅", "info"))
    sub = st.container() if container is None else container
    with sub:
        st.markdown(f"**{icon} {title}**")
        st.markdown(f"<span style='font-size:1.4em;font-weight:700'>{res['dose']}</span>",
                    unsafe_allow_html=True)
        if res.get("note"):
            st.caption(res["note"])
        if res.get("detail"):
            st.caption(f"依据：{res['detail']}")


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="抗生素剂量与 TDM 计算器", page_icon="💊", layout="wide")
    st.title("💊 抗生素剂量与 TDM 调整计算器")
    st.caption("医科院高水平项目 · 经验性抗生素剂量及 TDM 调整流程")

    # —— 侧边栏：选药 ——
    st.sidebar.title("选择抗生素")
    drug_keys = list(dc.DRUGS.keys())
    labels = [dc.DRUGS[k]["name"] for k in drug_keys]
    choice = st.sidebar.radio("药物", options=drug_keys, format_func=lambda k: dc.DRUGS[k]["name"])
    drug = dc.DRUGS[choice]

    st.sidebar.divider()
    st.sidebar.markdown(f"**{drug['ai_hint']}**")
    st.sidebar.caption("（依据 AI 病原学推测选药）")
    st.sidebar.divider()
    st.sidebar.markdown("**剂量取整规则**")
    st.sidebar.caption("抗生素单次剂量取整到 500/750/1000mg；多黏菌素取 50/100/150mg（1 万 u=1mg）")

    # —— 主区域头部 ——
    st.header(drug["name"])
    st.info(f"🎯 **TDM 目标**：{drug['tdm_target']}")

    left, right = st.columns([3, 2])

    # ========== 左：参数输入 ==========
    with left:
        st.subheader("① 患者参数")
        p = {}
        for key in drug["inputs"]:
            p[key] = render_input(key, st)

        st.subheader("② 用药指征确认")
        confirmed = st.checkbox(f"已确认：{drug['continue_hint']}", value=False)
        if not confirmed:
            st.warning("⚠️ 请确认细菌培养/药敏提示有该药使用指征后，再参考以下方案。", icon="⚠️")

        # ========== 计算 ==========
        st.subheader("③ 给药方案")
        loading = drug["loading"](p)
        maint = drug["maintenance"](p)

        c1, c2 = st.columns(2)
        with c1:
            show_result(None, "首剂量", loading)
        with c2:
            show_result(None, "维持剂量", maint)

    # ========== 右：TDM 调整 ==========
    with right:
        st.subheader("④ TDM 调整（48h 后）")
        tp = {}
        for key in drug["tdm_inputs"]:
            tp[key] = render_input(key, st)

        compute = st.button("计算 TDM 调整", type="primary", use_container_width=True)

        st.markdown("---")
        if compute:
            results = drug["tdm_adjust"]({**p, **tp})
            for i, r in enumerate(results):
                show_result(None, f"调整方案 {i+1}", r)
                st.markdown("")
        else:
            st.caption("填入实测浓度后点击「计算 TDM 调整」")

    st.divider()
    st.caption("🔁 每次调整剂量后 **48h 再次 TDM**，直到达标稳定。")
    st.caption("⚠️ 本工具依据 PPT 流程实现，部分公式/阈值含已知留白（见 README），仅供临床参考，最终方案由医师判定。")


if __name__ == "__main__":
    main()
