import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [설정] 페이지 레이아웃 고정 및 세션 안정화
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 세션 및 카테고리 설정 로드 (껐다 켜도 유지) ---
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
    # 초기 빈 데이터프레임 생성
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# --- [2] 보조 함수: 날짜, 금액 정제 및 지능형 분류 ---
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

def smart_categorize(content, is_income):
    if is_income: return "입실료"
    text = str(content).upper()
    if any(k in text for k in ['보증금', '반환', '퇴실']): return "보증금"
    if any(k in text for k in ['전기', '수도', '예스코', '가스', '한전', '공과금', 'SKB', 'SK인터넷', '인터넷', '세무', '부가세', '보험', 'ETAX', '대출', '소득세']): return "공과금"
    if any(k in text for k in ['쌀', '라면', '사리면', '진라면', '햇반', '오뚜기', '아몬드', '삼다수', '커피']): return "식품"
    if any(k in text for k in ['다이소', '비품', '세제', '휴지', '점보롤', '타월', '세탁', '봉투', '매트리스', '형광등', '건전지']): return "비품"
    if any(k in text for k in ['수리', '보수', '에어컨', '도어락', '보일러', '전구']): return "시설비"
    if any(k in text for k in ['임대료', '월세']): return "임대료"
    if any(k in text for k in ['인건비', '급여', '알바', '이명희']): return "인건비"
    return "기타"

# --- [3] 메인 화면 레이아웃 ---
st.title("🏠 율곡고시원 통합 정산 시스템")

# 사이드바 데이터 통합
st.sidebar.header("📂 데이터 통합")
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
            # 은행 파일 읽기
            if bank_file.name.endswith('.csv'):
                try: b_df = pd.read_csv(bank_file, encoding='utf-8-sig')
                except: b_df = pd.read_csv(bank_file, encoding='cp949')
            else:
                try: b_df = max(pd.read_html(bank_file), key=len)
                except: b_df = pd.read_excel(bank_file)
            
            h_idx = 0
            for i in range(min(20, len(b_df))):
                if '거래일시' in "".join(b_df.iloc[i].astype(str)): h_idx = i; break
            b_df.columns = b_df.iloc[h_idx]; b_df = b_df.iloc[h_idx+1:].reset_index(drop=True)
            
            new_rows = []
            for _, r in b_df.iterrows():
                if pd.isna(r.get('거래일시')): continue
                y, m, d_d = clean_date(r.get('거래일시'))
                vi, vo = clean_amt(r.get('맡기신금액', 0)), clean_amt(r.get('찾으신금액', 0))
                content = (str(r.get('기재내용','')) + " " + str(r.get('적요',''))).replace('nan','').strip()
                if "쿠팡" in content: continue
                yd = smart_categorize(content, vi > 0)
                new_rows.append({"연도":y,"월":m,"날짜":d_d,"내용":content,"용도":yd,"구분":c_map.get(yd,"비용"),"금액":vi if vi>0 else vo,"비고":str(r.get('적요',''))})
            
            # 쿠팡 파일 읽기
            c_df = pd.read_csv(coupang_file)
            for _, r in c_df.iterrows():
                amt = clean_amt(r.get('총결제금액(원)', 0))
                if amt > 0:
                    y, m, d_d = clean_date(r.get('주문일',''))
                    p_name = str(r.get('상품명',''))
                    yd = smart_categorize(p_name, False)
                    new_rows.append({"연도":y,"월":m,"날짜":d_d,"내용":p_name,"용도":yd,"구분":c_map.get(yd,"비용"),"금액":amt,"비고":"쿠팡구매"})
            
            if new_rows:
                st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame(new_rows)]).drop_duplicates(subset=['날짜','내용','금액'], keep='first').reset_index(drop=True)
                st.sidebar.success("통합 완료!")
                st.rerun()
        except Exception as e: st.sidebar.error(f"오류: {e}")

# 메인 탭 구성
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-2]: # [데이터 편집 탭] - 행 위치 고정의 핵심
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 수정 시 행 위치가 고정됩니다. 다른 탭을 다녀와도 수정한 내용이 유지됩니다.")
    
    cat_list = st.session_state.cat_df["항목명"].tolist()
    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))

    # 1. 에디터를 세션 스테이트와 직접 연결 (가장 안정적인 방식)
    # key를 주면 Streamlit이 내부적으로 스크롤 위치와 상태를 관리합니다.
    edited_df = st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        },
        key="main_data_editor" 
    )

    # 2. 데이터 업데이트 시 st.rerun()을 절대 호출하지 않음 (행 튀어오름 방지)
    if not edited_df.equals(st.session_state.master_df):
        # 용도가 변경되었을 경우 구분값만 조용히 업데이트
        edited_df['구분'] = edited_df['용도'].map(c_map).fillna(edited_df['구분'])
        st.session_state.master_df = edited_df
        # st.rerun()을 쓰지 않아야 스크롤이 유지됩니다.

with tabs[-1]: # [카테고리 설정 탭]
    st.subheader("⚙️ 카테고리 영구 저장")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True, key="cat_editor_key")
    if st.button("💾 이 설정 저장 (껐다 켜도 유지)"):
        st.session_state.cat_df = edited_cat
        edited_cat.to_csv(CAT_FILE, index=False)
        # 마스터 데이터의 구분값도 즉시 업데이트
        c_map = dict(zip(edited_cat['항목명'], edited_cat['연결구분']))
        st.session_state.master_df['구분'] = st.session_state.master_df['용도'].map(c_map).fillna(st.session_state.master_df['구분'])
        st.success("설정이 저장되었습니다!")
        st.rerun()

with tabs[0]: # [통합 리포트 탭]
    if not df.empty:
        plot_df = df[df['구분'] != '-'].copy()
        if not plot_df.empty:
            plot_df['금액'] = plot_df['금액'].apply(clean_amt)
            stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
            for c in ['수익', '비용']: 
                if c not in stats: stats[c] = 0
            st.metric("누적 순이익", f"{(stats['수익'].sum()-stats['비용'].sum()):,}원")
            st.plotly_chart(px.bar(stats, x='월', y=['수익', '비용'], barmode='group', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'}), use_container_width=True)
    else: st.info("사이드바에서 파일을 업로드해 주세요
