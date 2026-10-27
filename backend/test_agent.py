import json
import sys
from app.agent import run_agent

repo_dir, analysis_file = sys.argv[1], sys.argv[2]
data = json.load(open(analysis_file))
result = run_agent(data["analysis"], repo_dir,
                   on_event=lambda e: print(f"[{e['time']}] {e['agent']:<12} {e['action']:<18} {e['detail']}"))
print("\nSTATUS:", result["status"], "| steps used:", result["steps_used"])
print("STAGES:", result["stages"])
print(json.dumps(result["finding"], indent=1))
