import streamlit as st
import pandas as pd
from datetime import datetime
import time
import json
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. Google Sheets 설정
# ==========================================

# Streamlit Cloud에서는 secrets로 관리
# secrets.toml 또는 Streamlit Cloud Settings에서 설정

def get_google_sheet():
    """Google Sheet 연결"""
    try:
        # Streamlit Cloud secrets에서 credentials 가져오기
        creds_dict = st.secrets["gcp_service_account"]
        sheet_id = st.secrets["sheet_id"]

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except Exception as e:
        st.error(f"Google Sheets 연결 실패: {e}")
        return None

def save_to_sheets(responses, participant_name):
    """Google Sheets에 결과 저장 (한 번에 모든 행 추가)"""
    sheet = get_google_sheet()
    if sheet is None:
        return False

    try:
        # 헤더가 없으면 추가
        existing = sheet.get_all_values()
        if len(existing) == 0:
            headers = ["participant", "phase", "step", "choice", "ss_amount", "ll_amount", "rt_sec", "submitted_at"]
            sheet.append_row(headers)

        # 모든 데이터를 한 번에 추가 (순서 보장)
        submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for r in responses:
            row = [
                participant_name,
                r.get("phase", ""),
                r.get("step", ""),
                r.get("choice", ""),
                r.get("ss_amount", ""),
                r.get("ll_amount", ""),
                r.get("rt_sec", ""),
                submitted_at
            ]
            rows.append(row)

        # batch로 한 번에 추가
        sheet.append_rows(rows)
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

# ==========================================
# 2. 초기화 및 설정
# ==========================================

def init_session():
    if 'responses' not in st.session_state:
        st.session_state.responses = []

    if 'current_phase' not in st.session_state:
        st.session_state.current_phase = 'intro'

    if 'val_index' not in st.session_state:
        st.session_state.val_index = 2

    if 'step' not in st.session_state:
        st.session_state.step = 1

    if 'indifference_val' not in st.session_state:
        st.session_state.indifference_val = 550000

    if 'participant_name' not in st.session_state:
        st.session_state.participant_name = ""

    if 'question_start_time' not in st.session_state:
        st.session_state.question_start_time = time.time()

    # 중복 클릭 방지용
    if 'processing' not in st.session_state:
        st.session_state.processing = False

# ==========================================
# 3. Part 1~3: 한국형 금액 리스트 (KRW)
# ==========================================

VALUES_SMALL = [505000, 510000, 550000, 600000, 750000]
VALUES_LARGE = [5050000, 5100000, 5500000, 6000000, 7500000]

def get_baseline_options(phase, idx):
    idx = max(0, min(idx, 4))
    if phase == 'p3_large':
        base = 5000000
        ll_val = VALUES_LARGE[idx]
    else:
        base = 500000
        ll_val = VALUES_SMALL[idx]
    return base, ll_val

def update_index(phase, choice, current_idx):
    new_idx = current_idx
    if phase == 'p2_loss':
        if choice == 'SS': new_idx -= 1
        else: new_idx += 1
    else:
        if choice == 'SS': new_idx += 1
        else: new_idx -= 1
    return max(0, min(new_idx, 4))

# ==========================================
# 4. Part 4: Anomalies (원화 적용)
# ==========================================

def get_anomaly_question(step):
    ip_val = st.session_state.indifference_val
    base = 500000

    if step == 1:
        return {
            "ss_txt": f"12개월 후 {base:,}원 받기",
            "ll_txt": f"24개월 후 {ip_val:,}원 받기",
            "ss_val": base, "ll_val": ip_val
        }
    elif step == 2:
        diff = ip_val - base
        sub_val = base + (diff * 2)
        return {
            "ss_txt": f"지금 {base:,}원 받기",
            "ll_txt": f"24개월 후 {sub_val:,}원 받기",
            "ss_val": base, "ll_val": sub_val
        }
    elif step == 3:
        return {
            "ss_txt": "지금 500,000원 받기",
            "ll_txt": "1년 미루고 보너스 포함 600,000원 받기",
            "ss_val": 500000, "ll_val": 600000
        }
    elif step == 4:
        return {
            "ss_txt": "1년 뒤 600,000원을 지금으로 앞당겨 500,000원 받기",
            "ll_txt": "원래대로 1년 뒤 600,000원 받기",
            "ss_val": 500000, "ll_val": 600000
        }
    return None

# ==========================================
# 5. Part 5: Survey (한국 실정 반영)
# ==========================================

SURVEY_DATA = [
    {"id": "age", "type": "number", "q": "귀하의 연령(만 나이)은?", "min": 18, "max": 100},
    {"id": "gender", "type": "select", "q": "성별은?", "opts": ["남성", "여성", "기타"]},
    {"id": "edu", "type": "select", "q": "최종 학력은?",
     "opts": ["초등학교 졸업 이하", "중학교 졸업", "고등학교 졸업 (기술/직업)", "대학교 졸업 (학사)", "대학원 졸업 (석/박사 이상)"]},
    {"id": "job", "type": "select", "q": "현재 고용 상태는?",
     "opts": ["전일제 근무 (Full-time)", "파트타임 근무", "자영업/프리랜서", "구직 중", "미취업 (개인 사유)", "학생 (전업)", "은퇴"]},
    {"id": "income", "type": "number", "q": "세전 연간 총 소득(원)은?", "min": 0, "max": 10000000000},
    {"id": "debt", "type": "number", "q": "현재 총 부채(주택 대출 제외, 원)는?", "min": 0, "max": 10000000000},
    {"id": "asset", "type": "number", "q": "현재 총 자산(부동산/예금 포함, 원)은?", "min": 0, "max": 10000000000},
    {"id": "risk", "type": "slider", "q": "평소 위험을 감수하는 편입니까? (0: 전혀 아님 ~ 10: 매우 그렇다)", "min": 0, "max": 10},
    {"id": "outlook_nat", "type": "select", "q": "향후 1년 국가 경제 전망", "opts": ["좋아질 것이다", "비슷할 것이다", "나빠질 것이다"]},
    {"id": "outlook_per", "type": "select", "q": "향후 1년 개인 재정 전망", "opts": ["좋아질 것이다", "비슷할 것이다", "나빠질 것이다"]}
]

# ==========================================
# 6. 메인 실행 함수
# ==========================================

def reset_timer():
    st.session_state.question_start_time = time.time()

def get_rt():
    return round(time.time() - st.session_state.question_start_time, 3)

def record_response(choice, ss, ll, phase, step):
    rt = get_rt()
    st.session_state.responses.append({
        "phase": phase, "step": step, "choice": choice,
        "ss_amount": ss, "ll_amount": ll,
        "rt_sec": rt
    })

    if phase in ['p1_small', 'p2_loss', 'p3_large']:
        if phase == 'p1_small' and step == 3:
            current_ll = VALUES_SMALL[st.session_state.val_index]
            st.session_state.indifference_val = current_ll if choice == 'LL' else VALUES_SMALL[max(0, st.session_state.val_index-1)]

        if step < 3:
            st.session_state.val_index = update_index(phase, choice, st.session_state.val_index)
            st.session_state.step += 1
        else:
            st.session_state.step = 1
            st.session_state.val_index = 2
            if phase == 'p1_small': st.session_state.current_phase = 'p2_loss'
            elif phase == 'p2_loss': st.session_state.current_phase = 'p3_large'
            elif phase == 'p3_large': st.session_state.current_phase = 'p4_anomaly'

    elif phase == 'p4_anomaly':
        if step < 4: st.session_state.step += 1
        else:
            st.session_state.step = 1
            st.session_state.current_phase = 'p5_survey'

    reset_timer()

def main():
    st.set_page_config(page_title="의사결정 실험", page_icon="📋")
    init_session()
    phase = st.session_state.current_phase
    step = st.session_state.step

    # ===== INTRO: 참여자 이름 입력 =====
    if phase == 'intro':
        st.title("의사결정 실험")
        st.markdown("""
        **안내사항:**
        * 정답은 없습니다. 본인이 **실제로 선호하는 옵션**을 선택해주세요.
        * 모든 금액은 가상의 상황이지만, 실제 상황이라 가정하고 응답해 주세요.
        """)

        name = st.text_input("참여자 이름(또는 ID)을 입력해주세요:")
        if st.button("시작하기", type="primary"):
            if name.strip():
                st.session_state.participant_name = name.strip()
                st.session_state.current_phase = 'p1_small'
                reset_timer()
                st.rerun()
            else:
                st.warning("이름을 입력해주세요.")

    # ===== Part 1~3: 금액 선택 =====
    elif phase in ['p1_small', 'p2_loss', 'p3_large']:
        base, ll_val = get_baseline_options(phase, st.session_state.val_index)

        if phase == 'p2_loss':
            st.markdown(f"**{base:,}원**을 내야 하는 상황입니다. 어떻게 하시겠습니까?")
            t_ss, t_ll = f"지금 {base:,}원 내기", f"1년 뒤 {ll_val:,}원 내기"
        else:
            st.markdown(f"**{base:,}원**을 받을 수 있습니다. 어떻게 하시겠습니까?")
            t_ss, t_ll = f"지금 {base:,}원 받기", f"1년 뒤 {ll_val:,}원 받기"

        c1, c2 = st.columns(2)
        disabled = st.session_state.processing
        if c1.button(t_ss, use_container_width=True, disabled=disabled):
            st.session_state.processing = True
            record_response('SS', base, ll_val, phase, step)
            st.session_state.processing = False
            st.rerun()
        if c2.button(t_ll, use_container_width=True, disabled=disabled):
            st.session_state.processing = True
            record_response('LL', base, ll_val, phase, step)
            st.session_state.processing = False
            st.rerun()

    # ===== Part 4: Anomaly 질문 =====
    elif phase == 'p4_anomaly':
        q = get_anomaly_question(step)
        st.markdown("**다음 중 어떤 옵션을 선택하시겠습니까?**")

        c1, c2 = st.columns(2)
        disabled = st.session_state.processing
        if c1.button(q['ss_txt'], use_container_width=True, disabled=disabled):
            st.session_state.processing = True
            record_response('SS', q['ss_val'], q['ll_val'], phase, step)
            st.session_state.processing = False
            st.rerun()
        if c2.button(q['ll_txt'], use_container_width=True, disabled=disabled):
            st.session_state.processing = True
            record_response('LL', q['ss_val'], q['ll_val'], phase, step)
            st.session_state.processing = False
            st.rerun()

    # ===== Part 5: Survey =====
    elif phase == 'p5_survey':
        item = SURVEY_DATA[step-1]
        st.markdown(f"**{item['q']}**")
        disabled = st.session_state.processing

        if item['type'] == 'number':
            ans = st.number_input("입력", min_value=item['min'], max_value=item['max'], key=f"s_{step}", label_visibility="collapsed")
            if st.button("다음", disabled=disabled):
                st.session_state.processing = True
                record_response(ans, item['q'], "-", phase, step)
                if step < 10:
                    st.session_state.step += 1
                    reset_timer()
                    st.session_state.processing = False
                    st.rerun()
                else:
                    save_to_sheets(st.session_state.responses, st.session_state.participant_name)
                    st.session_state.current_phase = 'done'
                    st.session_state.processing = False
                    st.rerun()
        elif item['type'] == 'select':
            ans = st.radio("선택", item['opts'], key=f"s_{step}", label_visibility="collapsed")
            if st.button("다음", disabled=disabled):
                st.session_state.processing = True
                record_response(ans, item['q'], "-", phase, step)
                if step < 10:
                    st.session_state.step += 1
                    reset_timer()
                    st.session_state.processing = False
                    st.rerun()
                else:
                    save_to_sheets(st.session_state.responses, st.session_state.participant_name)
                    st.session_state.current_phase = 'done'
                    st.session_state.processing = False
                    st.rerun()
        elif item['type'] == 'slider':
            ans = st.slider("선택", item['min'], item['max'], 5, key=f"s_{step}", label_visibility="collapsed")
            if st.button("다음", disabled=disabled):
                st.session_state.processing = True
                record_response(ans, item['q'], "-", phase, step)
                if step < 10:
                    st.session_state.step += 1
                    reset_timer()
                    st.session_state.processing = False
                    st.rerun()
                else:
                    save_to_sheets(st.session_state.responses, st.session_state.participant_name)
                    st.session_state.current_phase = 'done'
                    st.session_state.processing = False
                    st.rerun()

    # ===== 완료 화면 =====
    elif phase == 'done':
        st.title("실험이 완료되었습니다")
        st.markdown("참여해 주셔서 감사합니다.")
        st.markdown("창을 닫아주세요.")

if __name__ == "__main__":
    main()
