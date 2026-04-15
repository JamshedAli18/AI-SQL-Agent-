import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from state    import SQLState
from tools    import execute_sql, get_schema
from database import create_database

# ── Setup ─────────────────────────────────────────────────
create_database()
llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.environ["GROQ_API_KEY"])

# ─────────────────────────────────────────────────────────
# NODE 1 — Schema Loader
# Loads DB schema into state so all nodes know the structure
# ─────────────────────────────────────────────────────────
def schema_loader_node(state: SQLState) -> dict:
    print("\n[schema] Loading database schema...")
    schema = get_schema.invoke({})
    print("[schema] Schema loaded ✅")
    return {"schema": schema}

# ─────────────────────────────────────────────────────────
# NODE 2 — SQL Generator
# Converts natural language question → SQL using schema as context
# ─────────────────────────────────────────────────────────
def sql_generator_node(state: SQLState) -> dict:
    print(f"\n[generator] Converting question to SQL...")

    prompt = f"""You are an expert SQL generator for SQLite.
Given the database schema and a question, generate ONLY the SQL query.
No explanation, no markdown, just the raw SQL query.

Database Schema:
{state['schema']}

Question: {state['question']}

Rules:
- Use only tables and columns that exist in the schema
- For SQLite use proper syntax
- Always use table aliases for joins
- Never add semicolons at the end

SQL Query:"""

    result = llm.invoke([HumanMessage(content=prompt)])
    sql    = result.content.strip()

    # Clean up any accidental markdown
    sql = sql.replace("```sql", "").replace("```", "").strip()
    print(f"[generator] Generated SQL: {sql}")
    return {"generated_sql": sql, "error": ""}

# ─────────────────────────────────────────────────────────
# NODE 3 — SQL Validator
# Checks if the SQL is a read or write operation
# ─────────────────────────────────────────────────────────
def sql_validator_node(state: SQLState) -> dict:
    print(f"\n[validator] Checking SQL type...")
    sql        = state["generated_sql"].strip().upper()
    is_write   = any(sql.startswith(op) for op in
                     ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"])
    op_type    = "WRITE ⚠️" if is_write else "READ ✅"
    print(f"[validator] Operation type: {op_type}")
    return {"is_write_op": is_write}

# ─────────────────────────────────────────────────────────
# NODE 4 — Human Review (only for write operations)
# Pauses graph and asks human to approve before writing to DB
# ─────────────────────────────────────────────────────────
def human_review_node(state: SQLState) -> dict:
    print(f"\n[review] Write operation detected — pausing for approval...")

    feedback = interrupt({
        "warning":      "⚠️  This is a WRITE operation!",
        "sql":          state["generated_sql"],
        "instructions": "Type 'approve' to execute or 'reject' to cancel."
    })

    approved = str(feedback).strip().lower() == "approve"
    print(f"[review] Human decision: {'approved ✅' if approved else 'rejected ❌'}")
    return {"approved": approved}

# ─────────────────────────────────────────────────────────
# NODE 5 — SQL Executor
# Runs the SQL query on the actual database
# ─────────────────────────────────────────────────────────
def sql_executor_node(state: SQLState) -> dict:
    print(f"\n[executor] Running SQL...")
    result = execute_sql.invoke({"sql": state["generated_sql"]})

    # Check if result is an error
    if result.startswith("ERROR:"):
        print(f"[executor] Error: {result}")
        return {"sql_result": "", "error": result}

    print(f"[executor] Query successful ✅")
    return {"sql_result": result, "error": ""}

# ─────────────────────────────────────────────────────────
# NODE 6 — Result Explainer
# Converts raw DB results → friendly plain English
# ─────────────────────────────────────────────────────────
def result_explainer_node(state: SQLState) -> dict:
    print(f"\n[explainer] Generating explanation...")

    prompt = f"""Convert these database query results into a clear,
friendly plain English explanation.

Original Question: {state['question']}
SQL Used: {state['generated_sql']}
Raw Results: {state['sql_result']}

Write a natural, conversational answer.
If it's a list, summarize the key points.
Be concise but complete."""

    result  = llm.invoke([HumanMessage(content=prompt)])
    explanation = result.content.strip()
    print(f"[explainer] Explanation ready ✅")
    return {
        "explanation": explanation,
        "messages":    [AIMessage(content=explanation)]
    }

# ─────────────────────────────────────────────────────────
# NODE 7 — Error Handler
# If SQL failed, asks LLM to fix it and retry
# ─────────────────────────────────────────────────────────
def error_handler_node(state: SQLState) -> dict:
    print(f"\n[error_handler] Fixing SQL error...")

    prompt = f"""The following SQL query failed. Fix it.

Schema:
{state['schema']}

Failed SQL: {state['generated_sql']}
Error: {state['error']}

Return ONLY the corrected SQL query, nothing else."""

    result     = llm.invoke([HumanMessage(content=prompt)])
    fixed_sql  = result.content.strip()
    fixed_sql  = fixed_sql.replace("```sql", "").replace("```", "").strip()

    print(f"[error_handler] Fixed SQL: {fixed_sql}")
    return {
        "generated_sql": fixed_sql,
        "error":         "",
        "retry_count":   state.get("retry_count", 0) + 1
    }

# ─────────────────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────────────────
def route_after_validator(state: SQLState) -> str:
    # Write operations need human approval
    if state["is_write_op"]:
        return "human_review"
    return "sql_executor"

def route_after_review(state: SQLState) -> str:
    # Human rejected → end
    if not state["approved"]:
        return "rejected"
    return "sql_executor"

def route_after_executor(state: SQLState) -> str:
    # SQL error and haven't retried too many times → fix it
    if state["error"] and state.get("retry_count", 0) < 2:
        return "error_handler"
    # SQL error but max retries hit → end
    if state["error"]:
        return "give_up"
    return "result_explainer"

def route_after_error(state: SQLState) -> str:
    return "sql_executor"   # always retry after fixing

# ─────────────────────────────────────────────────────────
# REJECTED / GIVE UP nodes (simple terminal nodes)
# ─────────────────────────────────────────────────────────
def rejected_node(state: SQLState) -> dict:
    msg = "Operation cancelled by user."
    print(f"\n[rejected] {msg}")
    return {"messages": [AIMessage(content=msg)]}

def give_up_node(state: SQLState) -> dict:
    msg = f"Sorry, I couldn't execute the query after retrying. Error: {state['error']}"
    print(f"\n[give_up] {msg}")
    return {"messages": [AIMessage(content=msg)]}

# ─────────────────────────────────────────────────────────
# BUILD GRAPH
# ─────────────────────────────────────────────────────────
def build_graph(memory):
    builder = StateGraph(SQLState)

    # Register all nodes
    builder.add_node("schema_loader",    schema_loader_node)
    builder.add_node("sql_generator",    sql_generator_node)
    builder.add_node("sql_validator",    sql_validator_node)
    builder.add_node("human_review",     human_review_node)
    builder.add_node("sql_executor",     sql_executor_node)
    builder.add_node("result_explainer", result_explainer_node)
    builder.add_node("error_handler",    error_handler_node)
    builder.add_node("rejected",         rejected_node)
    builder.add_node("give_up",          give_up_node)

    # Edges
    builder.add_edge(START,              "schema_loader")
    builder.add_edge("schema_loader",    "sql_generator")
    builder.add_edge("sql_generator",    "sql_validator")

    builder.add_conditional_edges("sql_validator",  route_after_validator)
    builder.add_conditional_edges("human_review",   route_after_review)
    builder.add_conditional_edges("sql_executor",   route_after_executor)
    builder.add_conditional_edges("error_handler",  route_after_error)

    builder.add_edge("result_explainer", END)
    builder.add_edge("rejected",         END)
    builder.add_edge("give_up",          END)

    return builder.compile(checkpointer=memory)

# ─────────────────────────────────────────────────────────
# MAIN — Chat loop
# ─────────────────────────────────────────────────────────
def main():
    memory  = MemorySaver()
    graph   = build_graph(memory)
    session = 1   # increment for new sessions

    print("\n" + "="*55)
    print("   🗄️  AI SQL AGENT — TechCorp Database")
    print("="*55)
    print("Ask anything about employees, products, sales.")
    print("Type 'exit' to quit | 'new' for a new session\n")

    # Show sample questions
    print("Sample questions:")
    print("  → Who are the top 5 highest paid employees?")
    print("  → What is the total sales amount per department?")
    print("  → Which product has the lowest stock?")
    print("  → How many employees are in Engineering?")
    print("  → Show me all sales above $4000\n")

    while True:
        question = input("You: ").strip()

        if not question:
            continue
        if question.lower() == "exit":
            print("Goodbye! 👋")
            break
        if question.lower() == "new":
            session += 1
            print(f"[new session started: {session}]\n")
            continue

        config = {"configurable": {"thread_id": f"sql_session_{session}"}}

        # ── Invoke graph ───────────────────────────────────
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

        # ── Handle interrupt (write operation approval) ────
        while True:
            state = graph.get_state(config)
            # Check if graph is paused at an interrupt
            if state.next and state.next[0] == "human_review":
                # Find interrupt data
                for task in state.tasks:
                    if hasattr(task, "interrupts") and task.interrupts:
                        interrupt_data = task.interrupts[0].value
                        print("\n" + "─"*50)
                        print(interrupt_data["warning"])
                        print(f"SQL: {interrupt_data['sql']}")
                        print("─"*50)
                        decision = input("Your decision (approve/reject): ").strip()
                        result   = graph.invoke(
                            Command(resume=decision),
                            config=config
                        )
                        break
            else:
                break

        # ── Print final answer ─────────────────────────────
        print(f"\n🤖 Agent: {result['messages'][-1].content}\n")
        print("─"*55)


# ✅ Add this at the bottom
memory = MemorySaver()
graph  = build_graph(memory)