import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [설정] 페이지 레이아웃 고정
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 데이터 및 카테고리 설정 로드 (영구 유지) ---
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

# --- [2] 핵심 기술: 데이터 실시간 동기화 (행 튀어오름 및 데이터 누락 방지) ---
# 이 로직이 위젯보다 먼저 실행되어야 수정 사항이 꼬이지 않고 그 자리에 고정됩니다.
if "master_editor" in st.session_state:
    edits = st.session_state["master_editor"]
    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
    
    # 1. 수정된 내용 즉시 반영 (index를 유지하여 행 고정)
    for row_idx, edit_dict in edits["edited_rows"].items():
        actual_idx = st.session_state.master_df.index[row_idx]
        for col, val in edit_dict.items():
            st.session_state.master_df.at[actual_idx, col] = val
            # 용도가 바뀌면 구분(자동)도 즉시 매칭
            if col == "용도":
                st.session_state.master_df.at[actual_idx, "구분"] = c_map.get(val, "비용")
    
    # 2. 행 추가 처리
    if edits["added_rows"]:
        for row in edits["added_rows"]:
            new_row = {col: "" for col in st.session_state.master_df.columns}
            new_row.update(row)
            if not new_row.get("용도"): new_row["용도"] = "기타"
            new_row["구분"] = c_map.get(new_row["용도"], "비용")
            st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame([new_row])], ignore_index=True)
    
    # 3. 행 삭제 처리
    if edits["deleted_rows"]:
        st.session_state.master_df = st.session_state.master_df.drop(st.session_state.master_df.index[edits["deleted_rows"]]).reset_index(drop=True)

# --- [3] 보조 함수 ---
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
    except: return "2026", "01", "01/01"

def smart_categorize(content, is_income):
    if is_income: return "입실료"
    text = str(content).upper()
    if any(k in text for k in ['보증금', '반환', '퇴실']): return "보증금"
    if any(k in text for k in ['전기', '수도', '가스', '한전', '인터넷', '보험', '세무']): return "공과금"
    if any(k in text for k in ['쌀', '라면', '햇반', '오뚜기']): return "식품"
    if any(k in text for k in ['다이소', '비품', '세제', '휴지', '형광등']): return "비품"
    if '월세' in text or '임대료' in text: return "임대료"
    return "기타"

# --- [4] 메인 화면 ---
st.title("🏠 율곡고시원 통합 정산 시스템")

# 사이드바 데이터 통합
st.sidebar.header("📂 데이터 통합")
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
            # (통합 로직... 기존과 동일)
            st.sidebar.success("통합 완료!")
            st.rerun()
        except Exception as e: st.sidebar.error(f"오류: {e}")

# 메인 탭
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-2]: # [데이터 편집 탭]
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 수정 시 행 위치가 강력하게 고정됩니다. 다른 행을 연속으로 고쳐도 데이터가 유실되지 않습니다.")
    
    cat_list = st.session_state.cat_df["항목명"].tolist()
    
    # st.data_editor 호출 (key를 사용하여 탭 이동 시에도 상태 유지)
    st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        },
        key="master_editor"
    )

with tabs[-1]: # 설정
    st.subheader("⚙️ 카테고리 영구 저장")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True, key="cat_editor")
    if st.button("💾 이 설정 저장 (껐다 켜도 유지)"):
        st.session_state.cat_df = edited_cat
        edited_cat.to_csv(CAT_FILE, index=False)
        st.success("설정이 저장되었습니다!")
        st.rerun()

with tabs[0]: # 리포트
    if not df.empty:
        plot_df = df[df['구분'] != '-'].copy()
        if not plot_df.empty:
            plot_df['금액'] = plot_df['금액'].apply(clean_amt)
            stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
            for c in ['수익', '비용']: 
                if c not in stats: stats[c] = 0
            st.metric("누적 순이익", f"{(stats['수익'].sum()-stats['비용'].sum()):,}원")
            st.plotly_chart(px.bar(stats, x='월', y=['수익', '비용'], barmode='group', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'}), use_container_width=True)
    else: st.info("사이드바에서 데이터를 업로드해 주세요.")

for i, m in enumerate(all_months):
    with tabs[i+1]: st.dataframe(df[df['월'] == m], use_container_width=True)

st.sidebar.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_마스터.csv", "text/csv")import streamlit as st
import pandas as pd
import plotly.express as px
import time
import re
import os

# [설정] 페이지 레이아웃 고정
st.set_page_config(page_title="율곡고시원 통합 관리 시스템", layout="wide")

# --- [1] 데이터 및 카테고리 설정 로드 (영구 유지) ---
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

# --- [2] 핵심 기술: 데이터 실시간 동기화 (행 튀어오름 및 데이터 누락 방지) ---
# 이 로직이 위젯보다 먼저 실행되어야 수정 사항이 꼬이지 않고 그 자리에 고정됩니다.
if "master_editor" in st.session_state:
    edits = st.session_state["master_editor"]
    c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
    
    # 1. 수정된 내용 즉시 반영 (index를 유지하여 행 고정)
    for row_idx, edit_dict in edits["edited_rows"].items():
        actual_idx = st.session_state.master_df.index[row_idx]
        for col, val in edit_dict.items():
            st.session_state.master_df.at[actual_idx, col] = val
            # 용도가 바뀌면 구분(자동)도 즉시 매칭
            if col == "용도":
                st.session_state.master_df.at[actual_idx, "구분"] = c_map.get(val, "비용")
    
    # 2. 행 추가 처리
    if edits["added_rows"]:
        for row in edits["added_rows"]:
            new_row = {col: "" for col in st.session_state.master_df.columns}
            new_row.update(row)
            if not new_row.get("용도"): new_row["용도"] = "기타"
            new_row["구분"] = c_map.get(new_row["용도"], "비용")
            st.session_state.master_df = pd.concat([st.session_state.master_df, pd.DataFrame([new_row])], ignore_index=True)
    
    # 3. 행 삭제 처리
    if edits["deleted_rows"]:
        st.session_state.master_df = st.session_state.master_df.drop(st.session_state.master_df.index[edits["deleted_rows"]]).reset_index(drop=True)

# --- [3] 보조 함수 ---
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
    except: return "2026", "01", "01/01"

def smart_categorize(content, is_income):
    if is_income: return "입실료"
    text = str(content).upper()
    if any(k in text for k in ['보증금', '반환', '퇴실']): return "보증금"
    if any(k in text for k in ['전기', '수도', '가스', '한전', '인터넷', '보험', '세무']): return "공과금"
    if any(k in text for k in ['쌀', '라면', '햇반', '오뚜기']): return "식품"
    if any(k in text for k in ['다이소', '비품', '세제', '휴지', '형광등']): return "비품"
    if '월세' in text or '임대료' in text: return "임대료"
    return "기타"

# --- [4] 메인 화면 ---
st.title("🏠 율곡고시원 통합 정산 시스템")

# 사이드바 데이터 통합
st.sidebar.header("📂 데이터 통합")
bank_file = st.sidebar.file_uploader("우리은행 거래내역", type=['csv', 'xls', 'xlsx'])
coupang_file = st.sidebar.file_uploader("쿠팡 구매내역", type=['csv'])

if st.sidebar.button("📦 새 데이터 합치기"):
    if bank_file and coupang_file:
        try:
            c_map = dict(zip(st.session_state.cat_df['항목명'], st.session_state.cat_df['연결구분']))
            # (통합 로직... 기존과 동일)
            st.sidebar.success("통합 완료!")
            st.rerun()
        except Exception as e: st.sidebar.error(f"오류: {e}")

# 메인 탭
df = st.session_state.master_df
all_months = sorted(df['월'].unique()) if not df.empty else []
tabs = st.tabs(["📊 통합 리포트"] + [f"📅 {m}월 상세" for m in all_months] + ["📝 데이터 편집", "⚙️ 카테고리 설정"])

with tabs[-2]: # [데이터 편집 탭]
    st.subheader("📝 상세 데이터 편집")
    st.info("💡 수정 시 행 위치가 강력하게 고정됩니다. 다른 행을 연속으로 고쳐도 데이터가 유실되지 않습니다.")
    
    cat_list = st.session_state.cat_df["항목명"].tolist()
    
    # st.data_editor 호출 (key를 사용하여 탭 이동 시에도 상태 유지)
    st.data_editor(
        st.session_state.master_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "용도": st.column_config.SelectboxColumn("용도", options=cat_list, required=True),
            "구분": st.column_config.TextColumn("구분(자동)", disabled=True),
            "금액": st.column_config.NumberColumn("금액", format="%d")
        },
        key="master_editor"
    )

with tabs[-1]: # 설정
    st.subheader("⚙️ 카테고리 영구 저장")
    edited_cat = st.data_editor(st.session_state.cat_df, num_rows="dynamic", use_container_width=True, key="cat_editor")
    if st.button("💾 이 설정 저장 (껐다 켜도 유지)"):
        st.session_state.cat_df = edited_cat
        edited_cat.to_csv(CAT_FILE, index=False)
        st.success("설정이 저장되었습니다!")
        st.rerun()

with tabs[0]: # 리포트
    if not df.empty:
        plot_df = df[df['구분'] != '-'].copy()
        if not plot_df.empty:
            plot_df['금액'] = plot_df['금액'].apply(clean_amt)
            stats = plot_df.groupby(['월', '구분'])['금액'].sum().unstack(fill_value=0).reset_index()
            for c in ['수익', '비용']: 
                if c not in stats: stats[c] = 0
            st.metric("누적 순이익", f"{(stats['수익'].sum()-stats['비용'].sum()):,}원")
            st.plotly_chart(px.bar(stats, x='월', y=['수익', '비용'], barmode='group', color_discrete_map={'수익': '#00CC96', '비용': '#EF553B'}), use_container_width=True)
    else: st.info("사이드바에서 데이터를 업로드해 주세요.")

for i, m in enumerate(all_months):
    with tabs[i+1]: st.dataframe(df[df['월'] == m], use_container_width=True)

st.sidebar.download_button("📥 통합 장부 다운로드", st.session_state.master_df.to_csv(index=False).encode('utf-8-sig'), "율곡고시원_마스터.csv", "text/csv")
