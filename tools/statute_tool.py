"""LangChain tool: retrieve relevant statute sections from the Chroma corpus."""
from __future__ import annotations

from langchain_core.tools import tool


@tool
def statute_retrieval_tool(query: str, code_regime: str = "BNS") -> str:
    """Retrieve relevant Indian statute sections from the legal corpus.

    Use this tool whenever you need to find the actual text of a law section.
    Always call this before citing any statute in your argument.

    Args:
        query: A description of the legal issue (e.g., "theft punishment section")
        code_regime: "BNS" for post-July 2024 offences, "IPC" for earlier offences

    Returns:
        Formatted list of relevant statute sections with their text.
    """
    from rag.retriever import retrieve

    chunks = retrieve(query=query, code_regime=code_regime, top_k=8)

    if not chunks:
        return (
            "No relevant statutes found in the corpus for this query. "
            "Do not cite any section that was not retrieved."
        )

    formatted = []
    for chunk in chunks:
        formatted.append(chunk.format_for_llm())

    return "\n---\n".join(formatted)
