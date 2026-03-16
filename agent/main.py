from analyzers.change_analyzer import get_changed_files
from analyzers.dependency_graph import build_graph
from simulation.impact_simulator import simulate_impact
from simulation.risk_scoring import compute_risk

def run_agent():

    repo_path = "."

    print("Detecting changed files...")

    changed = get_changed_files(repo_path)

    print("Changed files:", changed)

    print("Building system graph...")

    graph = build_graph()

    print("Running impact simulation...")

    impact = simulate_impact(graph, changed)

    print("Impacted services:", impact)

    risk = compute_risk(impact)

    print("Risk score:", risk)


if __name__ == "__main__":
    run_agent()