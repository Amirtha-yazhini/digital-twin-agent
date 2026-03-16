import networkx as nx

def build_graph():

    graph = nx.DiGraph()

    graph.add_edge("frontend", "api_gateway")
    graph.add_edge("api_gateway", "auth_service")
    graph.add_edge("auth_service", "database")

    return graph