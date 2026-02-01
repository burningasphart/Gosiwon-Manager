import streamlit as st
import pandas as pd
import plotly.express as px
import time

st.set_page_config(page_title="고시원 누적 정산 시스템", layout="wide")

# 숫자 정제 함수
def clean_amt(x):
    try:
        if pd.isna(x) or x == "": return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except:
        return 0

# 자동 카테고리 로직
def auto_categorize(content, income, outcome):
    if income > 0: return "수익", "입실료"
    content = str(content)
    if any(k in content for k in ['전기', '수도', '예스코', '가스', '한전']): return "비용", "공과금"
    if any(k in content for k in ['쌀', '라면', '우유', '커피', '식료', '아몬드']): return "비용", "식품"
    if any(k in content for k in ['다이소', '비품', '세제', '휴지', '점보롤', '타월']): return "비용", "비품"
    if '임대료' in content: return "비용", "임대료"
    if '보증금' in content: return "비용", "보증금"
    return "비용", "기타"

st.title("🏠 고시원 누적 정산 시스템 (대표님 전용)")

# --- 세션 상태 보존 ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])
if 'needs_download' not in st.session_state:
    st.session_state.needs_download = False

# --- 사이드바: 데이터 업로드 ---
st.sidebar.header("📂 1. 기존 데이터 불러오기")
prev_master = st.sidebar.file_uploader("과거 장부 파일 업로드", type=['csv'])

if st.sidebar.button("과거 기록 불러오기") and prev_master:
    st.session_state.master_df = pd.read_csv(prev_master)
    st.sidebar.success("과거 기록 로드 완료")

st.sidebar.divider()
st.sidebar.header("📂 2. 이번 달 데이터 추가")
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            # 은행/쿠팡 데이터 로직
            if bank_file.name.endswith('.csv'):
                bank_df = pd.read_csv(bank_file, skiprows=3)
            else:
                bank_file.seek(0)
                html_list = pd.read_html(bank_file)
                bank_df = max(html_list, key=len)
                header_row = 0
                for i in range(min(10, len(bank_df))):
                    if '거래일시' in str(bank_df.iloc[i].values):
                        header_row = i
                        break
                bank_df.columns = bank_df.iloc[header_row]
                bank_df = bank_df.iloc[header_row+1:].reset_index(drop=True)
            
            coupang_file.seek(0)
            coupang_df = pd.read_csv(coupang_file)
            
            new_rows = []
            for _, row in bank_df.iterrows():
                v_in, v_out = clean_amt(row.get('맡기신금액', 0)), clean_amt(row.get('찾으신금액', 0))
                v_sum, v_memo, v_date = str(row.get('적요', '')), str(row.get('기재내용', '')), str(row.get('거래일시', ''))
                if "쿠팡" in v_sum or "쿠팡" in v_memo or pd.isna(row.get('거래일시')): continue
                content = (v_memo + " " + v_sum).strip()
                gubun, yongdo = auto_categorize(content, v_in, v_out)
                new_rows.append({"연도": v_date[:4], "월": v_date[5:7], "날짜": v_date[5:10], "내용": content, "용도": yongdo, "구분": gubun, "금액": v_in if gubun=="수익" else v_out, "비고": v_sum})
            
            for _, row in coupang_df.iterrows():
                price = clean_amt(row.get('총결제금액(원)', 0))
                if price == 0: continue
                _, yongdo = auto_categorize(row.get('상품명', ''), 0, price)
                new_rows.append({"연도": str(row.get('주문일', ''))[:4], "월": str(row.get('주문일', ''))[6:8], "날짜": str(row.get('주문일', ''))[6:11], "내용": row.get('상품명', ''), "용도": yongdo, "구분": "비용", "금액": price, "비고": "쿠팡구매"})
            
            new_df = pd.DataFrame(new_rows)
            combined = pd.concat([st.session_state.master_df, new_df]).drop_duplicates(subset=['날짜', '내용', '금액'], keep='first')
            st.session_state.master_df = combined
            st.session_state.needs_download = True # 다운로드 알림 활성화
            st.sidebar.success("데이터 통합 완료!")
        except Exception as e:
            st.sidebar.error(f"오류: {e}")

st.sidebar.divider()
include_misc = st.sidebar.checkbox("사업 수익에 '기타' 지출 포함하기", value=False)

# --- 상단 알림창 (데이터가 변경되었을 때만 노출) ---
if st.session_state.needs_download:
    with st.container():
        st.warning("⚠️ 장부에 변경사항이 있습니다. 현재 상태를 파일로 저장하시겠습니까?")
        col1, col2 = st.columns([1, 8])
        with col1:
            # 이 버튼이 대표님이 말씀하신 '클릭만 하면 저장되는' 버튼입니다.
            st.download_button(
                label="✅ 지금 저장",
                data=st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'),
                file_name=f"고시원_누적장부_{time.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                on_click=lambda: st.session_state.update({"needs_download": False})
            )
        with col2:
            if st.button("나중에 하기"):
                st.session_state.needs_download = False

# --- 메인 화면 탭 구성 ---
all_months = sorted(st.session_state.master_df['월'].unique()) if not st.session_state.master_df.empty else []
tabs = st.tabs(["📊 통합 누적 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 전체 데이터 편집"])

# 1. 통합 리포트
with tabs[0]:
    df = st.session_state.master_df
    if not df.empty:
        df['금액'] = df['금액'].apply(clean_amt)
        plot_df = df[df['용도'] != '보증금'].copy()
        if not include_misc: plot_df = plot_df[plot_df['용도'] != '기타']
        
        stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
        for c in ['수익', '비용']: 
            if c not in stats: stats[c] = 0
        stats['순이익'] = stats['수익'] - stats['비용']

        c1, c2, c3 = st.columns(3)
        c1.metric("누적 수입", f"{stats['수익'].sum():,}원")
        c2.metric("누적 지출", f"{stats['비용'].sum():,}원")
        c3.metric("누적 순이익", f"{stats['순이익'].sum():,}원")

        st.subheader("📈 연간 추이")
        fig = px.bar(stats, x='월', y=['수익', '비용'], barmode='group', text_auto=',.0f', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터를 업로드해 주세요.")

# 3. 전체 편집 탭
with tabs[-1]:
    st.subheader("전체 장부 편집 및 현금 추가")
    edited = st.data_editor(st.session_state.master_df, use_container_width=True, num_rows="dynamic")
    if st.button("💾 장부 최종 저장"):
        st.session_state.master_df = edited
        st.session_state.needs_download = True # 편집 후에도 저장 알림 표시
        st.success("편집 내용이 반영되었습니다. 상단에서 저장을 눌러주세요!")
        st.rerun()

# 기존 사이드바 다운로드 버튼도 유지
st.sidebar.download_button("📥 통합 장부(Master) 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "고시원_마스터_백업.csv", "text/csv")
