# agent/main.py
import os
import sys
from analyzers.diff_fetcher import GitLabDiffFetcher
from analyzers.semantic_analyzer import SemanticAnalyzer
from analyzers.memory_store import MemoryStore
from integrations.mr_reporter import MRReporter
from integrations.issue_creator import IssueCreator
from integrations.socratic_dialogue import SocraticDialogue


def run():
    project_id = os.getenv("CI_PROJECT_ID")
    mr_iid = os.getenv("CI_MERGE_REQUEST_IID")
    mr_id = os.getenv("CI_MERGE_REQUEST_ID")

    if not mr_iid:
        print("Not a merge request pipeline. Skipping.")
        sys.exit(0)

    print(f"\n{'='*60}")
    print(f"Digital Twin Agent — MR !{mr_iid} | Project {project_id}")
    print(f"{'='*60}\n")

    # ─── STEP 1: Fetch diff & metadata ───────────────────────────
    fetcher = GitLabDiffFetcher()
    changes = fetcher.get_mr_changes(project_id, mr_iid)
    metadata = fetcher.get_mr_metadata(project_id, mr_iid)
    print(f"[1/5] Fetched {len(changes)} changed file(s): "
          f"{[c['file'] for c in changes]}")

    # ─── STEP 2: Load cross-MR memory ────────────────────────────
    memory = MemoryStore(project_id)
    history = memory.get_history()
    print(f"[2/5] Loaded {len(history)} past MR record(s) from memory")

    # ─── STEP 3: Claude semantic analysis ────────────────────────
    analyzer = SemanticAnalyzer()
    analysis = analyzer.analyze(changes, metadata, history)
    print(f"[3/5] Semantic analysis complete — "
          f"Risk Score: {analysis['risk_score']}/10")

    # ─── STEP 4: Take actions ─────────────────────────────────────
    reporter = MRReporter()
    issue_creator = IssueCreator()
    socratic = SocraticDialogue()

    # 4a. Post main analysis report to MR
    reporter.post_analysis(project_id, mr_iid, analysis, metadata)
    print("[4a/5] Posted semantic analysis report to MR")

    # 4b. Block MR if critical
    blocked = reporter.block_merge_if_critical(project_id, mr_iid, analysis)
    if blocked:
        print("[4b/5] ⛔ MR BLOCKED — critical risk detected")

    # 4c. Auto-create GitLab issue if risk >= 6
    if analysis["risk_score"] >= 6:
        issue_url = issue_creator.create_risk_issue(
            project_id, mr_iid, analysis, metadata
        )
        print(f"[4c/5] Created risk tracking issue: {issue_url}")
    else:
        print("[4c/5] Risk below threshold — no issue created")

    # 4d. Post Socratic question as a separate thread comment
    socratic.post_question(project_id, mr_iid, analysis, metadata)
    print("[4d/5] Posted Socratic reviewer question")

    # ─── STEP 5: Save to cross-MR memory ─────────────────────────
    memory.save_mr(mr_iid, analysis, metadata, changes)
    print("[5/5] Saved MR to memory store\n")

    print("✅ Digital Twin Agent complete.")
    print(f"{'='*60}\n")

    # Exit with error code if MR was blocked (fails the pipeline)
    if blocked:
        sys.exit(1)


if __name__ == "__main__":
    run()