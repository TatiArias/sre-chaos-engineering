#!/usr/bin/env python3
import subprocess
import time
import argparse
import sys
import json
import os

RESULTS_FILE = "chaos_results.json"

def run_command(cmd, timeout=300):
    """Execute shell command with timeout and return success status"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"

def deploy_broken_version():
    """Deploy unstable application version that will fail"""
    print(">> Deploying unstable version...")
    success, _, stderr = run_command("kubectl apply -f manifests/unstable/")
    if not success:
        print(f"Failed to deploy unstable version: {stderr}")
        return False
    print(">> Waiting for bad deployment to stabilize...")
    time.sleep(10) 
    return True

def trigger_chaos_workflow():
    """Launch Argo Workflow to execute chaos experiment"""
    print(">> Triggering chaos workflow...")
    # Clean up any existing workflow
    run_command("kubectl delete workflow pod-delete-chaos-experiment -n litmus --ignore-not-found=true")
    time.sleep(2)
    
    success, _, stderr = run_command("kubectl create -f manifests/chaos/pod-delete-workflow.yaml")
    if not success:
        print(f"Failed to trigger chaos workflow: {stderr}")
        return False
    
    print(">> Waiting for chaos workflow to initialize...")
    time.sleep(10)
    
    # Wait for chaos runner pod to appear and become active
    print(">> Waiting for chaos runner to start actively deleting pods...")
    for i in range(30):
        # Check if chaos runner pod exists and is running
        success, stdout, _ = run_command("kubectl get pods -n litmus -l job-name --no-headers 2>/dev/null | grep -i running")
        if success and "Running" in stdout:
            print(f">> Chaos runner detected! Waiting 5 more seconds for active deletion to begin...")
            time.sleep(5)
            return True
        time.sleep(1)
    
    print(">> Warning: Chaos runner not detected, proceeding anyway...")
    return True

def execute_rollback():
    """Execute rollback and measure time to successful recovery"""
    print(">> Executing rollback command...")
    start_time = time.time()
    success, _, stderr = run_command("kubectl rollout undo deployment/chaos-target-app -n chaos-app")
    if not success:
        print(f"Rollback command failed: {stderr}")
        return None
    
    print(">> Waiting for rollout to succeed...")
    success, _, stderr = run_command("kubectl rollout status deployment/chaos-target-app -n chaos-app --timeout=300s")
    end_time = time.time()
    
    if success:
        return end_time - start_time
    return None

def cleanup_chaos():
    """Clean up all chaos artifacts"""
    print(">> Cleaning up chaos artifacts...")
    run_command("kubectl delete workflow pod-delete-chaos-experiment -n litmus --ignore-not-found=true")
    run_command("kubectl delete chaosengine pod-delete-engine -n litmus --ignore-not-found=true")
    run_command("kubectl delete chaosexperiment pod-delete -n litmus --ignore-not-found=true")
    time.sleep(5)

def save_result(test_type, duration):
    """Save test result to JSON file for analysis"""
    data = {}
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                data = json.load(f)
        except:
            pass
    
    if test_type not in data:
        data[test_type] = []
    data[test_type].append(duration)
    
    with open(RESULTS_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print(f">> Result saved to {RESULTS_FILE}")

def measure_rollback_mttr(chaos_enabled=False):
    """Execute complete test scenario and measure MTTR"""
    label = "with-chaos" if chaos_enabled else "baseline"
    print(f"\nMEASURING MTTR: {label.upper()}")
    print("=" * 60)
    
    if not deploy_broken_version():
        return None

    if chaos_enabled:
        if not trigger_chaos_workflow():
            return None

    mttr = execute_rollback()
    cleanup_chaos()
    
    if mttr:
        print(f">> SUCCESS: Rollback took {mttr:.2f} seconds")
        save_result(label, mttr)
        return mttr
    else:
        print(">> FAILED: Rollback did not complete")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure MTTR for rollback procedures")
    parser.add_argument("--chaos", action="store_true", help="Enable chaos during rollback")
    parser.add_argument("--baseline", action="store_true", help="Run baseline test without chaos")
    args = parser.parse_args()
    
    if not args.chaos and not args.baseline:
        print("ERROR: Specify either --baseline or --chaos")
        print("Usage:")
        print("  Baseline test:  python3 scripts/measure-rollback-mttr.py --baseline")
        print("  Chaos test:     python3 scripts/measure-rollback-mttr.py --chaos")
        sys.exit(1)

    chaos = args.chaos
    measure_rollback_mttr(chaos)
