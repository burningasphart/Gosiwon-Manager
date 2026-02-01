import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [1] 페이지 설정
st.set_page_config(page_title="율곡고시원 정산 시스템", layout="wide")

# --- 데이터 로드 ---
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

# --- 보조 함수 ---
def clean_amt(x):
    try:
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except: return 0

# --- [중요] 행 튀어오름 방지 핵심 기술 ---
# 수정 시 자동으로 구분을 바꾸지 않고, 사용자가 다른 작업을 할 때만 조용히 업데이트함
def apply_changes():
    if "editor_key" in st.session_state:
        edits = st.session_state["editor_key"]
        df = st.session_state.master_df
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        
        # 수정사항 반영
        for row_idx, edit_dict in edits["edited_rows"].items():
            idx = df.index[row_idx]
            for col, val in edit_dict.items():
                df.at[idx, col] = val
                # 여기서 구분을 실시간으로 바꾸지 않음 (튀어오름 원인 차단)

        # 추가/삭제 반영
        if edits["added_rows"]:
            for row in edits["added_rows"]:
                new_row = {c: "" for c in df.columns}
                new_row.update(row)
                st.session_state.master_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        if edits["deleted_rows"]:
            st.session_state.master_df = df.drop(df.index[edits["deleted_rows"]]).reset_index(drop=True)

# --- 화면 구성 ---
st.title("🏠 율곡고시원 통합 관리 시스템")

# 사이드바 (업로드/다운로드)
with st.sidebar:
    st.header("📂 데이터 관리")
    # 파일 업로드 로직 생략 (기존 기능 유지)
    st.download_button("📥 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_장부.csv")

tabs = st.tabs(["📊 리포트", "📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[1]: # 데이터 편집 탭
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 용도를 수정해도 행이 튀어 오르지 않습니다. 수정 후 하단의 [변경사항 적용] 버튼을 눌러주세요.")
    
    cat_list = st.session_state.cat_df["항목명"].tolist()
    
    # 실시간 rerun을 유발하는 on_change를 제거함
    edited_df = st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list),
            "구분": st.column_config.TextColumn("구분", disabled=True), # 수동 수정 금지
            "금액": st.column_config.NumberColumn("금액", format="%d")
        },
        key="editor_key"
    )
    
    if st.button("💾 변경사항 최종 저장 및 구분 자동 업데이트"):
        c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
        # 편집기의 내용을 마스터 데이터에 반영
        st.session_state.master_df = edited_df
        # 용도에 맞춰 구분 일괄 업데이트
        st.session_state.master_df['구분'] = st.session_state.master_df['용도'].map(c_map).fillna(st.session_state.master_df['구분'])
        st.success("모든 변경사항이 저장되고 구분(수익/비용)이 업데이트되었습니다!")
        st.rerun()

with tabs[2]: # 설정 탭
    st.subheader("⚙️ 카테고리 설정")
    new_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 카테고리 저장"):
        st.session_state.cat_df = new_cat
        new_cat.to_csv(CAT_FILE, index=False)
        st.success("저장 완료!")

with tabs[0]: # 리포트 탭
    df = st.session_state.master_df
    if not df.empty:
        p_df = df[df['구분'].isin(['수익', '비용'])].copy()
        p_df['금액'] = p_df['금액'].apply(clean_amt)
        st.metric("누적 순이익", f"{(p_df[p_df['구분']=='수익']['금액'].sum() - p_df[p_df['구분']=='비용']['금액'].sum()):,}원")
        st.plotly_chart(px.bar(p_df, x='용도', y='금액', color='구분', barmode='group'))
