from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from best_agent_base import get_gemini


class State(TypedDict):
    question: str
    answer: str


def build_graph():
    llm = get_gemini()

    def answer_node(state: State) -> State:
        result = llm.invoke(state["question"])
        return {"question": state["question"], "answer": result.content}

    graph = StateGraph(State)
    graph.add_node("answer", answer_node)
    graph.add_edge(START, "answer")
    graph.add_edge("answer", END)
    return graph.compile()


def main():
    load_dotenv()
    app = build_graph()
    result = app.invoke({"question": "한 줄로 자기소개 해줘.", "answer": ""})
    print(result["answer"])


if __name__ == "__main__":
    main()
