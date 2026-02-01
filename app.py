import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re

st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 세션 초기화 ---
if 'cat_df' not in st.session_state:
    st.session_state.cat_df = pd.DataFrame({
        "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "시설비", "기타"],
        "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용", "비용"]
    })

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

if 'needs_download' not in st.session_state:
    st.session_state.needs_download = False

# --- [2] 보조 함수 ---
def smart_categorize(content, is_income):
    if is_income: return "입실료"
    text = str(content).upper()
    if any(k in text for k in ['보증금', '반환', '퇴실']): return "보증금"
    if any(k in text for k in ['전기', '수도', '예스코', '가스', '한전', '공과금', 'SKB', 'SK인터넷', '인터넷', '세무', '부가세', '보험', 'ETAX', '대출', '수도요금', '소득세', '지방세']): return "공과금"
    if any(k in text for k in ['쌀', '라면', '사리면', '진라면', '신라면', '햇반', '오뚜기', '아몬드', '곰곰', '바나나', '포카리', '하늘보리', '삼다수', '커피', '종이컵', '설탕']): return "식품"
    if any(k in text for k in ['다이소', '아성다', '비품', '세제', '휴지', '점보롤', '타월', '세탁', '봉투', '종량제', '매트리스', '형광등', '건전지', '샤워기', '뚫어뻥', '슬리퍼', '니트릴']): return "비품"
    if any(k in text for k in ['수리', '보수', '에어컨', '도어락', '보일러', '전구', '수도꼭지']): return "시설비"
    if any(k in text for k in ['임대료', '월세']): return "임대료"
    if any(k in text for k in ['인건비', '급여', '알바', '이명희']): return "인건비"
    return "기타"

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
        return "2026", "01", "01/01"
    except: return "2026", "01", "01/01"

st.title("🏠 율곡고시원 통합 정산 시스템")

# --- [3] 사이드바 ---
st.sidebar.header("📂 데이터 관리")
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            cat_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
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
                new_rows.append({"연도":y,"월":m,"날짜":d_d,"내용":content,"용도":yd,"구분":cat_map.get(yd,"비용"),"금액":vi if vi>0 else vo,"비고":str(r.get('적요',''))})
            c_df = pd.read_csv(coupang_file)
            for _, r in c_df.iterrows():
                amt = clean_amt(r.get('총결제금액(원)', 0))
                if amt > 0:
                    y, m, d_d = clean_date(r.get('주문일',''))
                    p_name = str(r.get('상품명',''))
                    yd = smart_categorize(p_name, False)
                    new_rows.append({"연도":y,"월":m,"날짜":d_d,"내용":p_name,"용도":yd,"구분":cat_map.get(yd,"비용"),"금액":amt,"비고":"쿠팡구매"})
            if new_rows:
                new_df = pd.DataFrame(new_rows)
                st.session_state.master_df = pd.concat([st.session_state.master_df, new_df]).drop_duplicates(subset=['날짜','내용','금액'], keep='first')
                st.session_state.needs_download = True
                st.sidebar.success("통합 완료!")
                st.rerun()
        except Exception as e: st.sidebar.error(f"오류: {e}")

# --- [4] 메인 화면 ---
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-1]: # 설정 탭
    st.subheader("⚙️ 카테고리 설정")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True)
    if st.button("설정 저장"):
        st.session_state.cat_df = edited_cat
        # 핵심 업데이트: 설정 저장 시 마스터 데이터의 '구분' 일괄 업데이트
        c_map = dict(zip(edited_cat['항목명'], edited_cat['연결구분']))
        st.session_state.master_df['구분'] = st.session_state.master_df['용도'].map(c_map).fillna(st.session_state.master_df['구분'])
        st.success("카테고리 설정이 반영되었습니다. 이제 모든 탭의 '구분'이 업데이트됩니다!")
        st.rerun()

with tabs[-2]: # 편집 탭
    st.subheader("📝 데이터 편집")
    cat_list = st.session_state.cat_df["항목명"].tolist()
    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
    edited = st.data_editor(st.session_state.master_df, use_container_width=True, num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        })
    if st.button("💾 장부 최종 저장"):
        edited['구분'] = edited['용도'].map(c_map).fillna(edited['구분'])
        st.session_state.master_df = edited
        st.session_state.needs_download = True
        st.success("저장 완료!")
        st.rerun()

with tabs[0]: # 리포트 탭
    if not df.empty:
        # 보정: 설정에서 '-'로 바뀐 항목은 리포트에서 자동 제외
        plot_df = df[df['구분'] != '-'].copy()
        if not plot_df.empty:
            plot_df['금액'] = plot_df['금액'].apply(clean_amt)
            stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
            for c in ['수익', '비용']: 
                if c not in stats: stats[c] = 0
            st.metric("누적 순이익 (제외 항목 제외)", f"{(stats['수익'].sum()-stats['비용'].sum()):,}원")
            st.plotly_chart(px.bar(stats, x='월', y=['수익', '비용'], barmode='group', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'}), use_container_width=True)
    else: st.info("데이터를 업로드해 주세요.")

for i, m in enumerate(all_months):
    with tabs[i+1]: st.dataframe(df[df['월'] == m], use_container_width=True)

st.sidebar.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_마스터.csv", "text/csv")
