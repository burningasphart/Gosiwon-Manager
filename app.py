import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [설정] 페이지 레이아웃 고정
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 데이터 및 카테고리 설정 로드 (껐다 켜도 유지) ---
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

# --- [2] 핵심: 탭 이동 및 행 수정 시 데이터 보존 로직 ---
def sync_data():
    """편집기의 변경사항을 화면 이동 없이 즉시 데이터에 박제함 (행 튀어오름 방지)"""
    if "editor_key" in st.session_state:
        edits = st.session_state["editor_key"]
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        
        # 수정된 행 처리 (인덱스를 건드리지 않음)
        for row_idx, edit_dict in edits["edited_rows"].items():
            idx = st.session_state.master_df.index[row_idx]
            for col, val in edit_dict.items():
                st.session_state.master_df.at[idx, col] = val
                # 용도가 바뀌면 구분(자동)도 조용히 업데이트
                if col == "용도":
                    st.session_state.master_df.at[idx, "구분"] = c_map.get(val, "비용")
        
        # 행 추가 처리
        for row in edits["added_rows"]:
            new_row = {col: "" for col in st.session_state.master_df.columns}
            new_row.update(row)
            if not new_row["용도"]: new_row["용도"] = "기타"
            new_row["구분"] = c_map.get(new_row["용도"], "비용")
            st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame([new_row])], ignore_index=True)

        # 행 삭제 처리
        if edits["deleted_rows"]:
            st.session_state.master_df = st.session_state.master_df.drop(st.session_state.master_df.index[edits["deleted_rows"]]).reset_index(drop=True)

# 실행 시마다 데이터 동기화 (탭 이동해도 유지되는 비결)
sync_data()

# --- [3] 메인 화면 ---
st.title("🏠 율곡고시원 통합 정산 시스템")

df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-2]: # [📝 데이터 편집] 탭
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 수정하던 행 그 자리에 그대로 머뭅니다. 다른 탭을 이동해도 작업 내용이 유지됩니다.")
    
    cat_list = st.session_state.cat_df["항목명"].tolist()
    
    # [핵심] st.rerun() 없이 on_change만 연결하여 행 튀어오름 차단
    st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        },
        key="editor_key" # 고정 키로 상태 보존
    )

with tabs[-1]: # [⚙️ 카테고리 설정] 탭
    st.subheader("⚙️ 카테고리 영구 저장")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True, key="cat_editor")
    if st.button("💾 이 설정으로 굳히기"):
        st.session_state.cat_df = edited_cat
        edited_cat.to_csv(CAT_FILE, index=False) # 파일로 저장 (영구 유지)
        st.success("이제 프로그램을 껐다 켜도 이 설정이 유지됩니다!")

# (리포트 및 월별 상세 코드는 동일하게 유지)
# ... [이하 생략]
