import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os

# [1] 기본 설정
st.set_page_config(page_title="율곡고시원 정산 시스템", layout="wide")

# 세션 초기화
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])
if 'cat_df' not in st.session_state:
    st.session_state.cat_df = pd.DataFrame({
        "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
        "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
    })

# --- [사이드바: 업로드 공간] ---
with st.sidebar:
    st.header("📂 데이터 통합")
    
    # 위젯의 label(이름)을 변경하여 먹통 현상을 강제 리셋합니다.
    st.write("▼ 파일을 클릭하거나 끌어다 놓으세요")
    
    # key값을 'bank_v5' 등으로 계속 바꿔주면 먹통된 위젯이 새로 고쳐집니다.
    bank_f = st.file_uploader("1. 우리은행 내역 선택", type=['csv', 'xlsx', 'xls'], key="bank_v101")
    coupang_f = st.file_uploader("2. 쿠팡 내역 선택", type=['csv'], key="coupang_v101")
    
    if st.button("📦 데이터 통합 실행", type="primary"):
        if bank_f and coupang_f:
            try:
                # 은행 파일 읽기
                if bank_f.name.endswith('.csv'):
                    try: b_df = pd.read_csv(bank_f, encoding='cp949')
                    except: b_df = pd.read_csv(bank_f, encoding='utf-8-sig')
                else:
                    b_df = pd.read_excel(bank_f, engine='openpyxl')
                
                # 쿠팡 파일 읽기
                c_df = pd.read_csv(coupang_f, encoding='utf-8-sig')

                # (이후 통합 로직 실행...)
                st.success("파일 읽기 성공!")
                # 데이터 처리 로직 생략 (위젯 복구에 집중)
                st.rerun()
            except Exception as e:
                st.error(f"파일을 읽는 도중 오류 발생: {e}")
        else:
            st.warning("두 파일을 모두 선택해야 버튼이 작동합니다.")

# --- [메인 화면] ---
tabs = st.tabs(["📊 리포트", "📝 전체편집", "⚙️ 설정"])
with tabs[1]:
    st.subheader("📝 통합 장부 편집")
    st.data_editor(st.session_state.master_df, use_container_width=True, num_rows="dynamic")
