import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [설정] 페이지 레이아웃 및 세션 안정화
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 세션 데이터 및 설정 로드 ---
CAT_FILE = "cat_settings.csv"

if 'cat_df' not in st.session_state:
    if os.path.exists(CAT_FILE):
        st.session_state.cat_df = pd.read_csv(CAT_FILE)
    else:
        st.session_state.cat_df = pd.DataFrame({
            "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
            "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
        })

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# --- [2] 핵심 기술: 행 튀어오름 방지 및 교차 수정 완벽 차단 ---
def on_edit_master():
    """편집 시 즉시 실행되어 행 위치를 고정하고 데이터를 동기화함"""
    state = st.session_state["master_editor"]
    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
    
    # 1. 수정된 내용 반영 (데이터프레임을 새로 갈아끼우지 않고 값만 수정)
    for row_idx, edit_dict in state["edited_rows"].items():
        idx = st.session_state.master_df.index[row_idx]
        for col, val in edit_dict.items():
            st.session_state.master_df.at[idx, col] = val
            if col == "용도":
                st.session_state.master_df.at[idx, "구분"] = c_map.get(val, "비용")
    
    # 2. 추가/삭제 처리
    if state["added_rows"]:
        for row in state["added_rows"]:
            new_row = {c: "" for c in st.session_state.master_df.columns}
            new_row.update(row)
            if not new_row["용도"]: new_row["용도"] = "기타"
            new_row["구분"] = c_map.get(new_row["용도"], "비용")
            st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame([new_row])], ignore_index=True)
            
    if state["deleted_rows"]:
        st.session_state.master_df = st.session_state.master_df.drop(st.session_state.master_df.index[state["deleted_rows"]]).reset_index(drop=True)

# --- [3] 보조 함수 ---
def clean_amt(x):
    try:
        if pd.isna(x) or str(x).strip() == "": return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except: return 0

def clean_date(date_val):
    try:
        d = str(date_val).strip()
        d = re.sub(r'[^0-9./-]', ' ', d).split()[0]
        d = d.replace('.', '-').replace('/', '-')
        parts = d.split('-')
        if len(parts) >= 3:
            return parts[0], parts[1].zfill(2), f"{parts[1].zfill(2)}/{parts[2].zfill(2)}"
        return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")
    except: return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")

# --- [4] 메인 화면 ---
st.title("🏠 율곡고시원 통합 정산 시스템")

# 사이드바 데이터 통합 (기존 로직 유지)
# ... [사이드바 합치기 버튼 등 기존 코드 동일] ...

# 메인 탭
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-2]: # [데이터 편집 탭]
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 수정 시 행 위치가 강력 고정됩니다. 다른 행을 연속으로 수정해도 튀어 오르지 않습니다.")
    cat_list = st.session_state.cat_df["항목명"].tolist()
    
    # [핵심] on_change 콜백만 사용하여 튀어오름 차단
    st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        },
        key="master_editor",
        on_change=on_edit_master # 수정 즉시 메모리만 업데이트
    )

with tabs[-1]: # [설정 탭]
    st.subheader("⚙️ 카테고리 영구 저장")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True, key="cat_editor")
    if st.button("💾 설정 저장 (껐다 켜도 유지)"):
        st.session_state.cat_df = edited_cat
        edited_cat.to_csv(CAT_FILE, index=False)
        st.success("설정이 저장되었습니다!")
        st.rerun()

# [리포트 및 월별 상세 코드 생략 - 기존과 동일]
