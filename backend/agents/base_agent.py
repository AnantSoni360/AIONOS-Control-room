"""
base_agent.py - LangGraph agent graph factory for AIONOS.

Creates a ReAct-style agent graph:
  START -> agent_node (LLM reasons + picks tool)
         -> tools_node (executes the selected tool)
         -> back to agent_node (loop)
         -> END (when LLM emits no more tool calls)

Supports two modes:
  - Standard (blocking):  create_agent_graph() -> invoke()
  - Streaming (SSE):      create_agent_graph() with event_queue -> invoke()

Phase 5: graph.invoke() runs inside a ThreadPoolExecutor with a configurable
timeout. AgentTimeoutError is raised if the agent exceeds AGENT_TIMEOUT_SECONDS.

Uses Groq Llama 3 via langchain-groq.
"""

import os
import queue as queue_module
import concurrent.futures
from typing import Annotated, Sequence, TypedDict, Optional

from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class AgentTimeoutError(Exception):
    """Raised when an agent run exceeds the configured timeout."""


# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    alert_id: int
    department: str
    run_id: str


# ---------------------------------------------------------------------------
# Graph Factory
# ---------------------------------------------------------------------------

def create_agent_graph(
    tools: list[BaseTool],
    system_prompt: str,
    policy_context: str = "",
    event_queue: Optional[queue_module.Queue] = None,
):
    """
    Build and compile a LangGraph ReAct agent.

    Args:
        tools:          List of LangChain tools the agent can call.
        system_prompt:  Department-specific system prompt grounded in SOP policy.
        policy_context: Optional RAG-retrieved SOP policy chunks.
        event_queue:    If provided, each step pushes a typed event dict for SSE.

    Returns:
        Compiled LangGraph graph ready to invoke.
    """
    full_prompt = (
        f"{policy_context}\n\n{system_prompt}"
        if policy_context
        else system_prompt
    )

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    ).bind_tools(tools)

    tool_node = ToolNode(tools)
    step_counter = [0]

    def agent_node(state: AgentState) -> dict:
        msgs = list(state["messages"])
        if not any(isinstance(m, SystemMessage) for m in msgs):
            msgs = [SystemMessage(content=full_prompt)] + msgs

        response = llm.invoke(msgs)
        step_counter[0] += 1

        if event_queue is not None:
            if isinstance(response.content, str) and response.content.strip():
                event_queue.put({
                    "type": "thinking",
                    "content": response.content.strip(),
                    "step": step_counter[0],
                })
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tc in response.tool_calls:
                    event_queue.put({
                        "type": "tool_call",
                        "name": tc["name"],
                        "args": tc.get("args", {}),
                        "step": step_counter[0],
                    })

        return {"messages": [response]}

    def streaming_tool_node(state: AgentState) -> dict:
        result = tool_node.invoke(state)
        if event_queue is not None:
            for msg in result.get("messages", []):
                if isinstance(msg, ToolMessage):
                    content = msg.content
                    if isinstance(content, list):
                        content = " ".join(str(c) for c in content)
                    event_queue.put({
                        "type": "tool_result",
                        "name": getattr(msg, "name", "tool"),
                        "content": str(content)[:500],
                        "step": step_counter[0],
                    })
        return result

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", streaming_tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


# ---------------------------------------------------------------------------
# Invoke with Timeout
# ---------------------------------------------------------------------------

def invoke_with_timeout(graph, initial_state: dict, timeout: int) -> dict:
    """
    Run graph.invoke() in a ThreadPoolExecutor with a hard timeout.

    Args:
        graph:         Compiled LangGraph graph.
        initial_state: Initial state dict.
        timeout:       Seconds before AgentTimeoutError is raised.

    Returns:
        Final state dict from graph.invoke().

    Raises:
        AgentTimeoutError: If execution exceeds timeout.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(graph.invoke, initial_state)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise AgentTimeoutError(
                f"Agent exceeded the {timeout}s timeout. "
                f"Alert reverted to Open. Please retry."
            )


# ---------------------------------------------------------------------------
# Result Extractor
# ---------------------------------------------------------------------------

def extract_result(final_state: AgentState) -> dict:
    """Pull a clean summary dict out of the final graph state."""
    messages = list(final_state.get("messages", []))
    steps = []
    for m in messages:
        role = type(m).__name__.replace("Message", "").lower()
        content = m.content if isinstance(m.content, str) else str(m.content)
        entry = {"role": role, "content": content}
        if hasattr(m, "tool_calls") and m.tool_calls:
            entry["tool_calls"] = [
                {"name": tc["name"], "args": tc["args"]}
                for tc in m.tool_calls
            ]
        steps.append(entry)

    final_msg = ""
    for m in reversed(messages):
        if hasattr(m, "content") and isinstance(m.content, str) and m.content.strip():
            final_msg = m.content
            break

    return {
        "run_id":        final_state.get("run_id", ""),
        "alert_id":      final_state.get("alert_id"),
        "department":    final_state.get("department", ""),
        "final_message": final_msg,
        "steps":         steps,
        "total_steps":   len(steps),
    }
