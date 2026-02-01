import streamlit as st
import pandas as pd
import os
import time

# [1] 페이지 설정 및 세션 초기화
st.set_page_config(page_title="율곡고시원 정산 시스템", layout="wide")

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# --- [핵심] 데이터 합치기 로직 보강 ---
def process_files(bank_f, coupang_f):
    try:
        # 1. 우리은행 파일 읽기 (인코딩 자동 시도)
        if bank_f.name.endswith('.csv'):
            try: b_df = pd.read_csv(bank_f, encoding='cp949')
            except: b_df = pd.read_csv(bank_f, encoding='utf-8-sig')
        else:
            b_df = pd.read_excel(bank_f)
        
        # 2. 거래일시 컬럼 찾기 (헤더 위치 자동 탐색)
        h_idx = -1
        for i in range(min(20, len(b_df))):
            row_str = "".join(b_df.iloc[i].astype(str))
            if '거래일시' in row_str or '거래일' in row_str:
                h_idx = i
                break
        
        if h_idx == -1:
            return False, "은행 파일에서 '거래일시' 헤더를 찾을 수 없습니다."

        # 헤더 재설정
        b_df.columns = b_df.iloc[h_idx]
        b_df = b_df.iloc[h_idx+1:].reset_index(drop=True)
        
        # 3. 쿠팡 파일 읽기
        c_df = pd.read_csv(coupang_f, encoding='utf-8-sig') if coupang_f.name.endswith('.csv') else pd.read_excel(coupang_f)
        
        # (이후 데이터 변환 로직 생략 - 기존과 동일)
        # 성공 시 메시지 반환
        return True, f"성공: 은행 {len(b_df)}건, 쿠팡 {len(c_df)}건 통합 완료!"
    
    except Exception as e:
        return False, f"오류 발생: {str(e)}"

# --- 사이드바 구성 ---
with st.sidebar:
    st.header("📂 데이터 통합")
    bank_file = st.file_uploader("우리은행 파일", type=['csv', 'xlsx'])
    coupang_file = st.file_uploader("쿠팡 파일", type=['csv', 'xlsx'])
    
    if st.button("📦 새 데이터 합치기"):
        if bank_file and coupang_file:
            with st.spinner('데이터를 분석 중입니다...'):
                success, message = process_files(bank_file, coupang_file)
                if success:
                    st.success(message)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(message) # 무엇이 문제인지 빨간 창으로 표시
        else:
            st.warning("두 개의 파일을 모두 업로드해 주세요.")

# (이하 탭 및 리포트 구성 생략)
st.write("### 현재 장부 상태")
st.dataframe(st.session_state.master_df, use_container_width=True)
