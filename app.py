import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 데이터 로드 로직 ---
CAT_FILE = "cat_settings.csv"
if 'cat_df' not in st.session_state:
    if os.path.exists(CAT_FILE): st.session_state.cat_df = pd.read_csv(CAT_FILE)
    else:
        st.session_state.cat_df = pd.DataFrame({
            "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
            "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
        })

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["날짜", "내용", "용도", "구분", "금액", "비고"])

# --- [2] 메인 화면 ---
st.title("🏠 율곡고시원 통합 관리 시스템")

# 사이드바 (업로드/다운로드)
with st.sidebar:
    st.header("📂 데이터 관리")
    # (파일 업로드 로직은 이전과 동일하므로 생략 가능하나, 구조 유지를 위해 배치)
    if st.button("🗑️ 장부 전체 초기화"):
        st.session_state.master_df = pd.DataFrame(columns=["날짜", "내용", "용도", "구분", "금액", "비고"])
        st.rerun()
    st.download_button("📥 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_장부.csv")

tabs = st.tabs(["📊 리포트", "📝 데이터 편집", "⚙️ 카테고리 설정"])

# --- [편집 탭] 행 튀어오름을 원천 차단하는 새 구조 ---
with tabs[1]:
    st.subheader("📝 데이터 편집 및 수정")
    df = st.session_state.master_df

    if not df.empty:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.write("▼ 수정할 행을 아래에서 클릭하여 선택하세요.")
            # 행 선택 기능 (여기서 선택해도 화면이 튀지 않음)
            selected_indices = st.multiselect("수정/삭제할 행 선택 (복수 선택 가능)", df.index)

        with col2:
            if selected_indices:
                st.warning(f"{len(selected_indices)}개의 행이 선택됨")
                new_yongdo = st.selectbox("변경할 용도 선택", st.session_state.cat_df["항목명"].tolist())
                
                if st.button("✅ 선택한 항목 일괄 변경"):
                    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
                    for idx in selected_indices:
                        st.session_state.master_df.at[idx, "용도"] = new_yongdo
                        st.session_state.master_df.at[idx, "구분"] = c_map.get(new_yongdo, "비용")
                    st.success("변경 완료!")
                    st.rerun()

                if st.button("🗑️ 선택한 항목 삭제"):
                    st.session_state.master_df = st.session_state.master_df.drop(selected_indices).reset_index(drop=True)
                    st.rerun()

        # 데이터 표 (여기서는 보기만 하고, 수정은 위 컨트롤러에서 함)
        st.dataframe(st.session_state.master_df, use_container_width=True)
    else:
        st.info("데이터가 없습니다. 파일을 업로드해 주세요.")

# --- [설정 탭] ---
with tabs[2]:
    st.subheader("⚙️ 카테고리 설정")
    new_cat_df = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 설정 저장"):
        st.session_state.cat_df = new_cat_df
        new_cat_df.to_csv(CAT_FILE, index=False)
        st.success("카테고리 설정이 저장되었습니다.")

# --- [리포트 탭] ---
with tabs[0]:
    if not df.empty:
        p_df = df[df['구분'] != '-'].copy()
        p_df['금액'] = pd.to_numeric(p_df['금액'], errors='coerce').fillna(0)
        income = p_df[p_df['구분'] == '수익']['금액'].sum()
        expense = p_df[p_df['구분'] == '비용']['금액'].sum()
        st.metric("현재 순이익", f"{int(income - expense):,}원")
        st.plotly_chart(px.bar(p_df, x='용도', y='금액', color='구분', barmode='group'))
