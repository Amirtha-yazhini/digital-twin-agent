def simulate_impact(graph, changed_files):

    impacted = set()

    for file in changed_files:

        service = file.replace(".py", "")

        if service in graph:

            neighbors = graph.successors(service)

            for n in neighbors:
                impacted.add(n)

    return list(impacted)