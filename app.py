import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from main import graph

# ── Page config ───────────────────────────────────────────
st.set_page_config(page_title="SQL Agent", page_icon=None, layout="centered")

st.markdown("""
<style>
    .block-container { max-width: 750px; padding-top: 2rem; }
    .stTextInput > div > div > input { border-radius: 8px; }
    .stButton > button {
        border-radius: 8px;
        border: 1px solid #ddd;
        background: white;
        color: #333;
        padding: 0.4rem 1.2rem;
    }
    .stButton > button:hover { background: #f5f5f5; }
    .sql-box {
        background: #f8f8f8;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-family: monospace;
        font-size: 0.85rem;
        color: #333;
        margin: 0.5rem 0;
    }
    .warning-box {
        background: #fff8f0;
        border: 1px solid #f0c080;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        font-size: 0.9rem;
    }
    .answer-box {
        background: #f0f7ff;
        border: 1px solid #c0d8f0;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────
st.title("SQL Agent")
st.caption("Ask questions about the TechCorp database in plain English.")
st.divider()

# ── Session state ─────────────────────────────────────────
if "session_id"    not in st.session_state:
    st.session_state.session_id    = "sql_session_1"
if "chat_history"  not in st.session_state:
    st.session_state.chat_history  = []
if "pending_write" not in st.session_state:
    st.session_state.pending_write = None   # holds interrupt data

# ── Sample questions ──────────────────────────────────────
st.markdown("**Try asking:**")
cols = st.columns(2)
samples = [
    "Who are the top 3 highest paid employees?",
    "Total sales amount per department?",
    "Which product has the lowest stock?",
    "How many employees are in Engineering?",
]
for i, sample in enumerate(samples):
    if cols[i % 2].button(sample, use_container_width=True):
        st.session_state.prefill = sample

st.divider()

# ── Chat history ──────────────────────────────────────────
for entry in st.session_state.chat_history:
    with st.chat_message(entry["role"]):
        if entry.get("sql"):
            st.markdown(f'<div class="sql-box">{entry["sql"]}</div>',
                        unsafe_allow_html=True)
        st.write(entry["content"])

# ── Write operation approval UI ───────────────────────────
if st.session_state.pending_write:
    data = st.session_state.pending_write
    st.markdown('<div class="warning-box"><strong>Write operation detected — approval required</strong></div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="sql-box">{data["sql"]}</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    if col1.button("Approve", use_container_width=True):
        config = {"configurable": {"thread_id": st.session_state.session_id}}
        result = graph.invoke(Command(resume="approve"), config=config)
        answer = result["messages"][-1].content
        st.session_state.chat_history.append({
            "role": "assistant", "content": answer, "sql": data["sql"]
        })
        st.session_state.pending_write = None
        st.rerun()

    if col2.button("Reject", use_container_width=True):
        config = {"configurable": {"thread_id": st.session_state.session_id}}
        graph.invoke(Command(resume="reject"), config=config)
        st.session_state.chat_history.append({
            "role": "assistant", "content": "Operation cancelled.", "sql": ""
        })
        st.session_state.pending_write = None
        st.rerun()

# ── Input ─────────────────────────────────────────────────
prefill  = st.session_state.pop("prefill", "")
question = st.chat_input("Ask a question about the database...")

if question or prefill:
    question = question or prefill
    config   = {"configurable": {"thread_id": st.session_state.session_id}}

    # Show user message
    st.session_state.chat_history.append({"role": "user", "content": question})

    with st.spinner("Thinking..."):
        result = graph.invoke(
            {
                "messages":      [HumanMessage(content=question)],
                "question":      question,
                "schema":        "",
                "generated_sql": "",
                "is_write_op":   False,
                "sql_result":    "",
                "explanation":   "",
                "error":         "",
                "retry_count":   0,
                "approved":      False
            },
            config=config
        )

    # Check if graph paused for write approval
    state = graph.get_state(config)
    paused = False
    for task in state.tasks:
        if hasattr(task, "interrupts") and task.interrupts:
            interrupt_data = task.interrupts[0].value
            st.session_state.pending_write = {
                "sql": interrupt_data.get("sql", ""),
            }
            paused = True
            break

    if not paused:
        answer  = result["messages"][-1].content
        sql_used = result.get("generated_sql", "")
        st.session_state.chat_history.append({
            "role":    "assistant",
            "content": answer,
            "sql":     sql_used
        })

    st.rerun()