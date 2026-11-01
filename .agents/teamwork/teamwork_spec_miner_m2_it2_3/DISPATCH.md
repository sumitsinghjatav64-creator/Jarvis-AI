# Task Assignment: Milestone 2 Iteration 2 Spec Miner (Test Contract & Stress Suite Alignment)

- **Role**: teamwork_spec_miner
- **Working Directory**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m2_it2_3
- **Project Root**: C:\jarvis\Mark-LV-main\Mark-LV-main
- **Original Request**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
- **Project Specification**: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
- **Test Files to Inspect**:
  - `tests/test_m2_challenger_stress.py`
  - `tests/test_widget_manager_oracle.js`
  - `.agents/teamwork/teamwork_reviewer_m2_2/adversarial_test.js`

## Context & Iteration 1 Gate Findings
The gate reviewers and challengers constructed empirical test scripts that surfaced:
1. `tests/test_widget_manager_oracle.js`: Suite 2 burst FIFO test failing (`[BURST FIFO FAILURE] FIFO capacity limit violated! Expected <= 4, got 7`).
2. `tests/test_m2_challenger_stress.py`: 2 xfailed tests for sparse array TypeError and FIFO capacity overflow under burst.
3. `.agents/teamwork/teamwork_reviewer_m2_2/adversarial_test.js`: DOM attribute breakout exploits (`<img src=x onerror=alert(1)>`) and burst eviction test.

## Your Objective
1. Inspect the 3 test scripts above and extract the exact input payloads, failure assertions, and success criteria.
2. Document the exact acceptance specifications that the remediated `ui_improved.html` must satisfy to achieve 100% pass rate across:
   - `node tests/test_widget_manager_oracle.js`
   - `pytest tests/test_m2_challenger_stress.py`
   - `node .agents/teamwork/teamwork_reviewer_m2_2/adversarial_test.js`
   - Full regression suite `pytest`
3. Write your extracted specifications in `handoff.md` and report back.


## 2026-10-31T10:08:08Z
[Message] timestamp=2026-10-31T10:08:08Z sender=6906300c-9137-4e62-90d0-c438dc9f10d1 priority=MESSAGE_PRIORITY_HIGH content=You are Milestone 2 Iteration 2 Spec Miner.
Read ORIGINAL_REQUEST.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
Read PROJECT.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
Read DISPATCH.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m2_it2_3\DISPATCH.md
Your working directory is: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m2_it2_3

Mine test failure assertions and success criteria from tests/test_widget_manager_oracle.js, tests/test_m2_challenger_stress.py, and .agents/teamwork/teamwork_reviewer_m2_2/adversarial_test.js. Provide exact acceptance specifications in handoff.md and report back via send_message to orchestrator (recipient: 6906300c-9137-4e62-90d0-c438dc9f10d1).
