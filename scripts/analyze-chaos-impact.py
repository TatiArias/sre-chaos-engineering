#!/usr/bin/env python3
import json
import os
import statistics

RESULTS_FILE = "chaos_results.json"

def analyze_mttr_results():
    """Analyze test results and generate impact report"""
    if not os.path.exists(RESULTS_FILE):
        print(f"ERROR: No results found in {RESULTS_FILE}")
        print("Run Phase 5 tests first to generate data.")
        return

    with open(RESULTS_FILE, 'r') as f:
        results = json.load(f)

    print("\nChaos Engineering Impact Analysis")
    print("=" * 60)
    print()

    if "baseline" not in results:
        print("ERROR: No baseline data found.")
        print("Run baseline tests with: python3 scripts/measure-rollback-mttr.py --baseline")
        return

    baseline_avg = statistics.mean(results["baseline"])
    baseline_stdev = statistics.stdev(results["baseline"]) if len(results["baseline"]) > 1 else 0

    print(f"Test Scenario          Avg MTTR    Std Dev    Impact")
    print("-" * 60)

    for scenario, times in sorted(results.items()):
        avg_time = statistics.mean(times)
        stdev = statistics.stdev(times) if len(times) > 1 else 0
        
        if scenario == "baseline":
            impact = 0.0
        else:
            impact = ((avg_time - baseline_avg) / baseline_avg) * 100
        
        print(f"{scenario:20} {avg_time:6.1f}s    ±{stdev:4.1f}s    {impact:+6.1f}%")

    print()
    print("Key Insights:")
    print(f"- Baseline rollback time: {baseline_avg:.1f}s (±{baseline_stdev:.1f}s)")
    
    if "with-chaos" in results:
        chaos_avg = statistics.mean(results["with-chaos"])
        impact_pct = ((chaos_avg - baseline_avg) / baseline_avg) * 100
        print(f"- Active pod deletion increases MTTR by {impact_pct:.1f}%")
        print(f"- Recovery takes an additional {chaos_avg - baseline_avg:.1f}s under chaos")
    
    print()
    print("SRE Recommendations:")
    print()
    print("1. Set SLA Targets Based on Chaos Conditions")
    print("   - Do NOT promise recovery times based on baseline tests")
    print("   - Account for real-world instability in SLA commitments")
    
    if "with-chaos" in results:
        chaos_avg = statistics.mean(results["with-chaos"])
        sla_target = chaos_avg * 1.2  # 20% buffer
        print(f"   - Recommend SLA: {sla_target:.0f}s (chaos MTTR + 20% buffer)")
    
    print()
    print("2. Improve System Resilience")
    print("   - Tune livenessProbe/readinessProbe for faster failure detection")
    print("   - Optimize container startup time to reduce MTTR")
    print("   - Consider PodDisruptionBudgets to limit chaos impact")
    
    print()
    print("3. Automate Chaos Testing")
    print("   - Schedule these workflows weekly in staging environments")
    print("   - Block production deployments if chaos tests fail")
    print("   - Track MTTR trends over time to validate improvements")
    
    print()
    print("4. Document Findings")
    print("   - Add these metrics to your incident response runbooks")
    print("   - Use this data during post-incident reviews")
    print("   - Present findings to leadership for infrastructure investments")
    print()

if __name__ == "__main__":
    analyze_mttr_results()
