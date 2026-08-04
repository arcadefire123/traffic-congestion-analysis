import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="교차로 혼잡 조기경보", layout="wide")

BASE = Path(__file__).parent.parent


@st.cache_data
def load():
    return pd.read_csv(BASE / "data" / "dashboard_data.csv")


agg = load()

st.title("교차로 혼잡 조기경보 대시보드")
st.caption("성남대로 3개 교차로 · 2023.11 ~ 2025.09 · 원본 366만 건 분석 결과")

# ── 사이드바 ──
st.sidebar.header("설정")
inter = st.sidebar.selectbox("교차로", sorted(agg.교차로.unique()))
thr = st.sidebar.slider("경보 임계값 (혼잡지수 %)", 10, 50, 30, 5)
st.sidebar.caption("낮출수록 민감 (놓침 감소, 헛경보 증가)")

st.sidebar.divider()
st.sidebar.markdown(
    """**경보 3단계**

- 정상: 혼잡지수 < 20
- 주의: 20 ~ 30 → 1시간 후 혼잡 확률 14.6%
- 경보: 30 이상 → 1시간 후 혼잡 확률 70.8%

---
**혼잡지수 정의**

(1 − 실제속도 ÷ 자유속도) × 100

자유속도는 각 구간이 한산할 때의 중앙값 속도"""
)

sub = agg[(agg.교차로 == inter) & (agg.임계값 == thr)].copy()

# ── 요약 지표 ──
w = sub.혼잡률 * sub.표본
c1, c2, c3, c4 = st.columns(4)
c1.metric("평일 혼잡률", f"{w.sum() / sub.표본.sum():.1f}%")
c2.metric("평균 통행량", f"{(sub.평균교통량 * sub.표본).sum() / sub.표본.sum():.0f} 대/시")
hourly = sub.groupby("시").apply(
    lambda x: (x.혼잡률 * x.표본).sum() / x.표본.sum(), include_groups=False)
c3.metric("최혼잡 시각", f"{hourly.idxmax()}시")
c4.metric("분석 구간 수", f"{sub.groupby(['접근로','이동류']).ngroups} 개")

# ── 시간대별 혼잡률 ──
st.subheader("시간대별 혼잡률")
h = hourly.round(1).reset_index()
h.columns = ["시", "혼잡률"]
fig = px.bar(h, x="시", y="혼잡률", color="혼잡률",
             color_continuous_scale="YlOrRd", labels={"혼잡률": "혼잡률(%)"})
fig.update_layout(xaxis=dict(dtick=1))
st.plotly_chart(fig, use_container_width=True)

# ── 구간별 히트맵 ──
st.subheader("구간별 · 시간대별 혼잡 현황")
hm = sub.copy()
hm["구간"] = hm.접근로.str.replace(" 방면", "", regex=False) + " " + hm.이동류
piv = hm.pivot_table(index="구간", columns="시", values="혼잡률")
piv = piv.loc[piv.mean(axis=1).sort_values(ascending=False).index]

fig2 = px.imshow(piv, color_continuous_scale="YlOrRd", aspect="auto",
                 labels=dict(color="혼잡률(%)", x="시", y=""))
fig2.update_layout(height=max(300, 40 * len(piv)), xaxis=dict(dtick=1))
st.plotly_chart(fig2, use_container_width=True)
st.caption("색이 진할수록 혼잡. 위쪽일수록 평균 혼잡률이 높은 구간입니다.")

# ── 경보 대상 ──
st.subheader("경보 대상 구간 (현재 임계값 기준)")
alert = (sub.groupby(["접근로", "이동류"], observed=True)
           .apply(lambda x: pd.Series({
               "혼잡률": round((x.혼잡률 * x.표본).sum() / x.표본.sum(), 1),
               "평균교통량": round((x.평균교통량 * x.표본).sum() / x.표본.sum(), 0),
           }), include_groups=False).reset_index())
alert["지체노출"] = (alert.혼잡률 / 100 * alert.평균교통량).round(0)
alert = alert.sort_values("지체노출", ascending=False).reset_index(drop=True)
alert.index += 1

st.dataframe(alert, use_container_width=True)
st.caption("지체노출 = 혼잡률 × 평균교통량. 개선 우선순위의 근거 지표입니다.")

st.info("경보 임계값을 조정하면 민감도가 달라집니다. "
        "낮추면 놓치는 혼잡이 줄지만 헛경보가 늘어납니다.")
