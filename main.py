import os
import streamlit as st
import anthropic
from dotenv import load_dotenv
from rag import build_index, query_context, is_index_ready

# 로컬: .env 로드 / Streamlit Cloud: st.secrets 사용
load_dotenv()

def get_secret(key: str, default: str = "") -> str:
    """st.secrets(Streamlit Cloud) → os.environ(.env) → default 순으로 조회."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.environ.get(key, default)

# ────────────────────────────────────────────────────────────────────────────
# 천안 봉명동 성당 프로필 (시스템 프롬프트에 항상 포함)
# ────────────────────────────────────────────────────────────────────────────
PROFILE = """
당신은 천안 봉명동 성당의 안내 및 정보 제공 어시스턴트입니다.

[성당 기본 정보]
성당명: 천안 봉명동 성당
주소: 충남 천안시 동남구 우영3길 15 (우편번호: 31152)
전화: 041-574-7411 (사무실) / 041-574-7412 (사제관)
홈페이지: http://cafe.daum.net/920church
주임신부: 안두현 미카엘 신부

[전례(미사) 시간]
평일 미사:
- 월요일: 06:30
- 수요일, 금요일: 10:00
- 화요일, 목요일: 19:00

주일 미사:
- 토요일 저녁: 19:00
- 일요일 새벽: 06:30
- 일요일 교중: 10:00

특별 미사:
- 매월 첫 목요일 저녁미사 후
- 매월 첫 토요일 10:00 성모신심미사

[단체 모임 안내]
- 제대회: 8월 25일(화)
- 울뜨레야: 8월 28일(목)
- 사목회: 8월 30일(주일)

[기도해 주세요]
다음 분들의 치유와 평안을 위해 기도해주세요:
- 박종임 루시아
- 백옥분 수산나
- 최승룡 마태오
- 김공례 마리아
- 이명순 로사리아
- 김영세 소사아가다
- 최순남 마리아
- 현상원 데레사

[답변 방침]
- 성당 기본 정보 질문: 위 정보로 정확하게 답변
- PDF 자료가 제공된 경우: 해당 자료를 우선 참고하여 답변하고, 출처를 명시
- 모르는 내용: "확인할 수 없는 내용입니다"라고 답변
- 모든 답변은 한국어로 친절하게
""".strip()


# ────────────────────────────────────────────────────────────────────────────
# Streamlit 설정
# ────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="천안 봉명동 성당 안내",
    page_icon="⛪",
    layout="centered",
)

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
html, body, [class*="css"] { font-family: 'Pretendard Variable', Pretendard, sans-serif; }
.source-box { background:#f0f9ff; border-left:3px solid #0891b2; padding:0.6rem 0.8rem;
              font-size:0.82rem; color:#334155; border-radius:0 6px 6px 0; margin-top:0.5rem; }
</style>
""", unsafe_allow_html=True)

st.title("⛪ 천안 봉명동 성당 안내")
st.caption("천안 봉명동 성당의 정보 및 미사 안내에 대해 무엇이든 물어보세요.")

# ────────────────────────────────────────────────────────────────────────────
# 사이드바 — API 키 & RAG 인덱스 관리
# ────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")

    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = st.text_input(
            "Anthropic API 키",
            type="password",
            placeholder="sk-ant-...",
        )

    st.divider()
    st.subheader("📚 PDF 인덱스")

    ready = is_index_ready()
    if ready:
        st.success("인덱스 준비 완료")
    else:
        st.warning("인덱스 없음 — 관리자 로그인 후 빌드하세요.")

    # 관리자 잠금 영역
    if "admin_unlocked" not in st.session_state:
        st.session_state.admin_unlocked = False

    if not st.session_state.admin_unlocked:
        admin_pw = st.text_input("관리자 비밀번호", type="password", placeholder="비밀번호 입력…")
        if st.button("로그인", use_container_width=True):
            correct = get_secret("ADMIN_PASSWORD", "admin1234")
            if admin_pw == correct:
                st.session_state.admin_unlocked = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    else:
        st.success("관리자 모드")
        if st.button("🔄 인덱스 빌드 / 재빌드", use_container_width=True):
            with st.spinner("PDF 파싱 & 임베딩 중… (첫 실행 시 수 분 소요)"):
                try:
                    count = build_index()
                    st.success(f"완료: {count}개 청크 저장")
                    st.rerun()
                except FileNotFoundError as e:
                    st.error(str(e))
        if st.button("잠금", use_container_width=True, type="secondary"):
            st.session_state.admin_unlocked = False
            st.rerun()

    use_rag = st.toggle("RAG 사용", value=ready, disabled=not ready)

    st.divider()
    n_results = st.slider("검색할 청크 수", 1, 10, 5)

if not api_key:
    st.info("사이드바에서 Anthropic API 키를 입력하세요.")
    st.stop()

client = anthropic.Anthropic(api_key=api_key)

# ────────────────────────────────────────────────────────────────────────────
# 대화
# ────────────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("성당 정보가 궁금하신가요? 질문을 입력하세요…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # RAG 검색
    rag_context = ""
    if use_rag and ready:
        rag_context = query_context(prompt, n_results=n_results)

    # 시스템 프롬프트 구성
    system_prompt = PROFILE
    if rag_context:
        system_prompt += f"\n\n[PDF 자료에서 검색된 관련 내용]\n{rag_context}"

    with st.chat_message("assistant"):
        with st.spinner("답변 생성 중…"):
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                system=system_prompt,
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
            )
            answer = response.content[0].text

        st.markdown(answer)

        # 참고 자료 표시
        if rag_context:
            sources = set()
            for line in rag_context.splitlines():
                if line.startswith("[출처:"):
                    src = line.split("|")[0].replace("[출처:", "").strip()
                    sources.add(src)
            if sources:
                st.markdown(
                    "<div class='source-box'>📄 참고 자료: "
                    + ", ".join(sorted(sources))
                    + "</div>",
                    unsafe_allow_html=True,
                )

        st.session_state.messages.append({"role": "assistant", "content": answer})

# 초기화 버튼
if st.session_state.messages:
    if st.button("대화 초기화", type="secondary"):
        st.session_state.messages = []
        st.rerun()
