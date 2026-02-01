import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re

st.set_page_config(page_title="고시원 통합 관리 시스템", layout="wide")

# --- [1] 세션 초기화 (최우선 실행) ---
if 'cat_df' not in st.session_state:
    st.session_state.cat_df = pd.DataFrame({
        "항목명": ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "기타"],
        "연결구분": ["수익", "비용", "비용", "비용", "비용", "-", "비용", "비용"]
    })

if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

if 'history' not in st.session_state:
    st.session_state.history = [st.session_state.master_df.copy()]

if 'history_ptr' not in st.session_state:
    st.session_state.history_ptr = 0

if 'needs_download' not in st.session_state:
    st.session_state.needs_download = False

# --- [2] 보조 함수 ---
def save_history(df):
    st.session_state.history = st.session_state.history[:st.session_state.history_ptr + 1]
    st.session_state.history.append(df.copy())
    st.session_state.history_ptr += 1
    if len(st.session_state.history) > 10:
        st.session_state.history.pop(0)
        st.session_state.history_ptr -= 1

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
    except:
        return time.strftime("%Y"), time.strftime("%m"), time.strftime("%m/%d")

st.title("🏠 고시원 누적 정산 시스템")

# --- [3] 사이드바 ---
st.sidebar.header("📂 데이터 로드")
prev_master = st.sidebar.file_uploader("기존 마스터 파일(.csv)", type=['csv'])
if st.sidebar.button("장부 불러오기") and prev_master:
    try:
        st.session_state.master_df = pd.read_csv(prev_master)
        save_history(st.session_state.master_df)
        st.sidebar.success("로드 완료")
    except: st.sidebar.error("파일 형식 오류")

st.sidebar.divider()
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            # 카테고리 매핑 안전하게 생성
            cat_data = st.session_state.cat_df
            cat_map = dict(zip(cat_data['항목명'], cat_data['연결구분']))
            
            # 은행 파일 읽기
            if bank_file.name.endswith('.csv'):
                try: bank_df = pd.read_csv(bank_file, encoding='utf-8-sig')
                except: bank_df = pd.read_csv(bank_file, encoding='cp949')
            else:
                try:
                    bank_file.seek(0)
                    bank_df = max(pd.read_html(bank_file), key=len)
                except:
                    bank_file.seek(0)
                    bank_df = pd.read_excel(bank_file)

            # 헤더 찾기
            h_idx = 0
            for i in range(min(20, len(bank_df))):
                if '거래일시' in "".join(bank_df.iloc[i].astype(str)):
                    h_idx = i; break
            bank_df.columns = bank_df.iloc[h_idx]
            bank_df = bank_df.iloc[h_idx+1:].reset_index(drop=True)
            
            # 데이터 가공
            new_rows = []
            for _, r in bank_df.iterrows():
                if pd.isna(r.get('거래일시')): continue
                y, m, d_d = clean_date(r.get('거래일시'))
                vi, vo = clean_amt(r.get('맡기신금액', 0)), clean_amt(r.get('찾으신금액', 0))
                content = (str(r.get('기재내용','')) + " " + str(r.get('적요',''))).replace('nan','').strip()
                if "쿠팡" in content: continue
                new_rows.append({"연도":y,"월":m,"날짜":d_d,"내용":content,"용도":"기타","구분":cat_map.get("기타","비용"),"금액":vi if vi>0 else vo,"비고":str(r.get('적요',''))})

            # 쿠팡 가공
            coupang_df = pd.read_csv(coupang_file)
            for _, r in coupang_df.iterrows():
                amt = clean_amt(r.get('총결제금액(원)', 0))
                if amt > 0:
                    y, m, d_d = clean_date(r.get('주문일',''))
                    new_rows.append({"연도":y,"월":m,"날짜":d_d,"내용":str(r.get('상품명','')),"용도":"기타","구분":cat_map.get("기타","비용"),"금액":amt,"비고":"쿠팡구매"})
            
            if new_rows:
                new_df = pd.DataFrame(new_rows)
                st.session_state.master_df = pd.concat([st.session_state.master_df, new_df]).drop_duplicates(subset=['날짜','내용','금액'], keep='first')
                save_history(st.session_state.master_df)
                st.session_state.needs_download = True
                st.sidebar.success("통합 완료!")
                st.rerun()
        except Exception as e: st.sidebar.error(f"오류: {e}")

st.sidebar.divider()
include_misc = st.sidebar.checkbox("사업 수익에 '기타' 지출 포함하기", value=False)

# --- [4] 메인 화면 ---
if st.session_state.needs_download:
    st.warning("⚠️ 저장되지 않은 데이터가 있습니다.")
    st.download_button("✅ 지금 파일로 저장", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), f"고시원장부_{time.strftime('%Y%m%d')}.csv", "text/csv", on_click=lambda: st.session_state.update({"needs_download": False}))

df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-1]: # 카테고리 설정
    st.subheader("⚙️ 용도 및 연결구분 설정")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True)
    if st.button("설정 내용 저장"):
        st.session_state.cat_df = edited_cat
        c_map = dict(zip(edited_cat['항목명'], edited_cat['연결구분']))
        st.session_state.master_df['구분'] = st.session_state.master_df['용도'].map(c_map).fillna(st.session_state.master_df['구분'])
        st.success("카테고리 설정 완료!")
        st.rerun()

with tabs[-2]: # 데이터 편집
    st.subheader("📝 상세 편집")
    cat_list = st.session_state.cat_df["항목명"].tolist()
    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
    
    if st.button("⬅️ 되돌리기") and st.session_state.history_ptr > 0:
        st.session_state.history_ptr -= 1
        st.session_state.master_df = st.session_state.history[st.session_state.history_ptr].copy()
        st.rerun()
    
    edited = st.data_editor(st.session_state.master_df, use_container_width=True, num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        })
    
    if st.button("💾 장부 최종 저장"):
        edited['구분'] = edited['용도'].map(c_map).fillna(edited['구분'])
        st.session_state.master_df = edited
        save_history(edited)
        st.session_state.needs_download = True
        st.success("저장 완료!")
        st.rerun()

with tabs[0]: # 통합 리포트
    if not df.empty:
        plot_df = df[df['구분'] != '-'].copy()
        if not include_misc: plot_df = plot_df[plot_df['용도'] != '기타']
        
        if not plot_df.empty:
            plot_df['금액'] = plot_df['금액'].apply(clean_amt)
            stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
            for c in ['수익', '비용']: 
                if c not in stats: stats[c] = 0
            st.metric("누적 순이익", f"{(stats['수익'].sum()-stats['비용'].sum()):,}원")
            st.plotly_chart(px.bar(stats, x='월', y=['수익', '비용'], barmode='group', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'}), use_container_width=True)
    else: st.info("사이드바에서 파일을 업로드해 주세요.")

for i, m in enumerate(all_months):
    with tabs[i+1]: st.dataframe(df[df['월'] == m], use_container_width=True)

st.sidebar.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "고시원_마스터.csv", "text/csv")
