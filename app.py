import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re

st.set_page_config(page_title="고시원 누적 정산 시스템", layout="wide")

# --- 세션 상태 보존 ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])
if 'categories' not in st.session_state:
    # 기본 카테고리 설정
    st.session_state.categories = ["입실료", "공과금", "식품", "비품", "임대료", "보증금", "인건비", "기타"]
if 'history' not in st.session_state:
    st.session_state.history = [st.session_state.master_df.copy()]
if 'history_ptr' not in st.session_state:
    st.session_state.history_ptr = 0
if 'needs_download' not in st.session_state:
    st.session_state.needs_download = False

def save_history(df):
    st.session_state.history = st.session_state.history[:st.session_state.history_ptr + 1]
    st.session_state.history.append(df.copy())
    st.session_state.history_ptr += 1
    if len(st.session_state.history) > 20:
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
            y, m, dv = parts[0], parts[1].zfill(2), parts[2].zfill(2)
            return y, m, f"{m}/{dv}"
        return "2026", "01", "01/01"
    except: return "2026", "01", "01/01"

def auto_categorize(content, income, outcome):
    if income > 0: return "수익", "입실료"
    content = str(content)
    if any(k in content for k in ['전기', '수도', '예스코', '가스', '한전']): return "비용", "공과금"
    if any(k in content for k in ['쌀', '라면', '우유', '커피', '식료', '아몬드']): return "비용", "식품"
    if any(k in content for k in ['다이소', '비품', '세제', '휴지', '점보롤', '타월']): return "비용", "비품"
    if '임대료' in content: return "비용", "임대료"
    if '보증금' in content: return "비용", "보증금"
    if '인건비' in content: return "비용", "인건비"
    return "비용", "기타"

st.title("🏠 고시원 누적 정산 시스템")

# --- 사이드바 ---
st.sidebar.header("📂 데이터 관리")
prev_master = st.sidebar.file_uploader("과거 장부(.csv)", type=['csv'])
if st.sidebar.button("과거 기록 불러오기") and prev_master:
    st.session_state.master_df = pd.read_csv(prev_master)
    save_history(st.session_state.master_df)
    st.sidebar.success("로드 완료")

st.sidebar.divider()
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            if bank_file.name.endswith('.csv'): bank_df = pd.read_csv(bank_file, skiprows=3)
            else:
                bank_file.seek(0)
                html_list = pd.read_html(bank_file)
                bank_df = max(html_list, key=len)
                header_row = 0
                for i in range(min(15, len(bank_df))):
                    if '거래일시' in str(bank_df.iloc[i].values): header_row = i; break
                bank_df.columns = bank_df.iloc[header_row]
                bank_df = bank_df.iloc[header_row+1:].reset_index(drop=True)
            
            coupang_file.seek(0)
            coupang_df = pd.read_csv(coupang_file)
            new_rows = []
            for _, r in bank_df.iterrows():
                if pd.isna(r.get('거래일시')): continue
                y, m, d_d = clean_date(r.get('거래일시'))
                vi, vo = clean_amt(r.get('맡기신금액', 0)), clean_amt(r.get('찾으신금액', 0))
                sum_m, memo = str(r.get('적요', '')), str(r.get('기재내용', ''))
                if "쿠팡" in sum_m or "쿠팡" in memo: continue
                content = (memo + " " + sum_m).strip()
                gubun, yongdo = auto_categorize(content, vi, vo)
                if vi > 0 or vo > 0: new_rows.append({"연도": y, "월": m, "날짜": d_d, "내용": content, "용도": yongdo, "구분": gubun, "금액": vi if gubun=="수익" else vo, "비고": sum_m})
            for _, r in coupang_df.iterrows():
                price = clean_amt(r.get('총결제금액(원)', 0))
                if price > 0:
                    y, m, d_d = clean_date(r.get('주문일', ''))
                    _, yongdo = auto_categorize(r.get('상품명', ''), 0, price)
                    new_rows.append({"연도": y, "월": m, "날짜": d_d, "내용": r.get('상품명', ''), "용도": yongdo, "구분": "비용", "금액": price, "비고": "쿠팡구매"})
            
            new_df = pd.DataFrame(new_rows)
            combined = pd.concat([st.session_state.master_df, new_df]).drop_duplicates(subset=['날짜', '내용', '금액'], keep='first')
            st.session_state.master_df = combined
            save_history(combined)
            st.session_state.needs_download = True
            st.sidebar.success("통합 완료")
        except Exception as e: st.sidebar.error(f"오류: {e}")

st.sidebar.divider()
include_misc = st.sidebar.checkbox("사업 수익에 '기타' 지출 포함하기", value=False)

if st.session_state.needs_download:
    st.warning("⚠️ 데이터가 변경되었습니다. 저장하시겠습니까?")
    st.download_button("✅ 지금 파일로 저장", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), f"고시원_장부_{time.strftime('%Y%m%d')}.csv", "text/csv", on_click=lambda: st.session_state.update({"needs_download": False}))

# --- 메인 탭 구성 ---
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[0]: # 통합 리포트
    if not df.empty:
        df['금액'] = df['금액'].apply(clean_amt)
        plot_df = df[df['용도'] != '보증금'].copy()
        if not include_misc: plot_df = plot_df[plot_df['용도'] != '기타']
        stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
        for c in ['수익', '비용']: 
            if c not in stats: stats[c] = 0
        c1, c2, c3 = st.columns(3)
        c1.metric("누적 수입", f"{stats['수익'].sum():,}원")
        c2.metric("누적 지출", f"{stats['비용'].sum():,}원")
        c3.metric("누적 순이익", f"{(stats['수익'].sum()-stats['비용'].sum()):,}원")
        st.plotly_chart(px.bar(stats, x='월', y=['수익', '비용'], barmode='group', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'}), use_container_width=True)
    else: st.info("데이터를 업로드해주세요.")

for i, m in enumerate(all_months):
    with tabs[i+1]: st.dataframe(df[df['월'] == m], use_container_width=True)

with tabs[-2]: # 데이터 편집
    st.subheader("📝 데이터 상세 편집")
    col1, col2, _ = st.columns([1, 1, 5])
    with col1:
        if st.button("⬅️ 이전"):
            if st.session_state.history_ptr > 0:
                st.session_state.history_ptr -= 1
                st.session_state.master_df = st.session_state.history[st.session_state.history_ptr].copy()
                st.rerun()
    with col2:
        if st.button("이후 ➡️"):
            if st.session_state.history_ptr < len(st.session_state.history) - 1:
                st.session_state.history_ptr += 1
                st.session_state.master_df = st.session_state.history[st.session_state.history_ptr].copy()
                st.rerun()
    
    edited = st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "구분": st.column_config.SelectboxColumn("구분", options=["수익", "비용"], required=True),
            "용도": st.column_config.SelectboxColumn("용도", options=st.session_state.categories, required=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        }
    )
    if st.button("💾 편집 내용 저장"):
        st.session_state.master_df = edited
        save_history(edited)
        st.session_state.needs_download = True
        st.success("저장되었습니다!")
        st.rerun()

with tabs[-1]: # 카테고리 설정 (새로 추가된 기능!)
    st.subheader("⚙️ 용도 카테고리 관리")
    st.write("표에 새로운 항목을 추가하거나 기존 이름을 수정하세요.")
    
    # 카테고리 리스트를 데이터프레임으로 변환하여 편집
    cat_df = pd.DataFrame(st.session_state.categories, columns=["항목명"])
    edited_cat = st.data_editor(cat_df, num_rows="dynamic", use_container_width=True)
    
    if st.button("🛠 카테고리 목록 업데이트"):
        st.session_state.categories = edited_cat["항목명"].dropna().unique().tolist()
        st.success("카테고리 목록이 업데이트되었습니다! 이제 [데이터 편집] 탭에서 확인하실 수 있습니다.")

st.sidebar.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "고시원_마스터.csv", "text/csv")
