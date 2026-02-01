import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="고시원 통합 관리 시스템", layout="wide")

def clean_amt(x):
    try:
        if pd.isna(x) or x == "": return 0
        s = "".join(filter(str.isdigit, str(x).split('.')[0]))
        return int(s) if s else 0
    except:
        return 0

def auto_categorize(content, income, outcome):
    if income > 0: return "수익", "입실료"
    content = str(content)
    if any(k in content for k in ['전기', '수도', '예스코', '가스', '한전']): return "비용", "공과금"
    if any(k in content for k in ['쌀', '라면', '우유', '커피', '식료', '아몬드']): return "비용", "식품"
    if any(k in content for k in ['다이소', '비품', '세제', '휴지', '점보롤', '타월']): return "비용", "비품"
    if '임대료' in content: return "비용", "임대료"
    if '보증금' in content: return "비용", "보증금"
    return "비용", "기타"

st.title("🏠 고시원 통합 관리 시스템 (대표님 전용)")

# --- 세션 상태 보존 ---
if 'final_df' not in st.session_state:
    st.session_state.final_df = pd.DataFrame(columns=["연도", "월", "날짜", "내용", "용도", "구분", "금액", "비고"])

# 사이드바 설정
st.sidebar.header("📁 데이터 업로드")
bank_file = st.sidebar.file_uploader("우리은행 거래내역 (XLS/CSV)", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역 (CSV)", type=['csv'])

# 데이터 불러오기 버튼 (이 버튼을 누를 때만 파일에서 새로 읽어옴)
if st.sidebar.button("📦 파일 데이터 불러오기"):
    if bank_file and coupang_file:
        try:
            # 은행 읽기
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
            
            # 쿠팡 읽기
            coupang_file.seek(0)
            coupang_df = pd.read_csv(coupang_file)
            
            new_data = []
            for _, row in bank_df.iterrows():
                v_in, v_out = clean_amt(row.get('맡기신금액', 0)), clean_amt(row.get('찾으신금액', 0))
                v_sum, v_memo, v_date = str(row.get('적요', '')), str(row.get('기재내용', '')), str(row.get('거래일시', ''))
                if "쿠팡" in v_sum or "쿠팡" in v_memo or pd.isna(row.get('거래일시')): continue
                content = (v_memo + " " + v_sum).strip()
                gubun, yongdo = auto_categorize(content, v_in, v_out)
                new_data.append({"연도": v_date[:4], "월": v_date[5:7], "날짜": v_date[5:10], "내용": content, "용도": yongdo, "구분": gubun, "금액": v_in if gubun=="수익" else v_out, "비고": v_sum})
            
            for _, row in coupang_df.iterrows():
                price = clean_amt(row.get('총결제금액(원)', 0))
                _, yongdo = auto_categorize(row.get('상품명', ''), 0, price)
                new_data.append({"연도": str(row.get('주문일', ''))[:4], "월": str(row.get('주문일', ''))[6:8], "날짜": str(row.get('주문일', ''))[6:11], "내용": row.get('상품명', ''), "용도": yongdo, "구분": "비용", "금액": price, "비고": "쿠팡구매"})
            
            # 파일에서 가져온 데이터로 세션 업데이트
            st.session_state.final_df = pd.DataFrame(new_data)
            st.sidebar.success("파일 데이터를 성공적으로 로드했습니다!")
        except Exception as e:
            st.sidebar.error(f"오류: {e}")

st.sidebar.divider()
include_misc = st.sidebar.checkbox("사업 수익에 '기타' 지출 포함하기", value=False)

# --- 탭 구성 ---
tab1, tab2 = st.tabs(["📊 월간 통합 대시보드", "📝 데이터 상세 정리 및 추가"])

with tab2:
    st.subheader("데이터 상세 내역")
    st.info("💡 1. 파일을 올린 후 [파일 데이터 불러오기] 버튼을 누르세요. 2. 수정이나 현금 추가 후 반드시 아래 [저장하기] 버튼을 누르세요.")
    
    # 세션에 저장된 데이터를 에디터에 표시
    edited_df = st.data_editor(st.session_state.final_df, use_container_width=True, num_rows="dynamic", key="main_editor")
    
    if st.button("✅ 변경사항 및 추가내역 저장하기"):
        st.session_state.final_df = edited_df
        st.success("데이터가 안전하게 저장되었습니다!")
        st.rerun()

with tab1:
    df = st.session_state.final_df
    if not df.empty:
        df['금액'] = df['금액'].apply(clean_amt)
        # 필터링
        plot_df = df[df['용도'] != '보증금'].copy()
        if not include_misc:
            plot_df = plot_df[plot_df['용도'] != '기타']
        
        if not plot_df.empty:
            monthly_stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
            for c in ['수익', '비용']: 
                if c not in monthly_stats: monthly_stats[c] = 0
            monthly_stats['순이익'] = monthly_stats['수익'] - monthly_stats['비용']

            c1, c2, c3 = st.columns(3)
            c1.metric("총 수입", f"{monthly_stats['수익'].sum():,}원")
            c2.metric("총 지출", f"{monthly_stats['비용'].sum():,}원")
            c3.metric("순이익", f"{(monthly_stats['수익'].sum() - monthly_stats['비용'].sum()):,}원")

            st.subheader("📅 월별 누적 추이")
            fig = px.bar(monthly_stats, x='월', y=['수익', '비용'], barmode='group', text_auto=',.0f', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'})
            st.plotly_chart(fig, use_container_width=True)
            st.table(monthly_stats.style.format("{:,}원", subset=['수익', '비용', '순이익']))
    else:
        st.info("데이터가 없습니다. 파일을 먼저 불러와 주세요.")

st.sidebar.download_button("💾 전체 장부 다운로드(CSV)", st.session_state.final_df.to_csv(index=False).encode('utf-8-sig'), "고시원_통합장부.csv", "text/csv")
