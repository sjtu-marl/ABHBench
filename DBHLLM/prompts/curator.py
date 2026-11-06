SUMMARY_BASE = """You are tasked with analyzing a specific action and its consequences. Below, you will find:
- **Contextual Information**: Background information related to the situation.
- **Action**: The specific action under analysis.
- **Observations Before the Action**: Observations leading up to the action.
- **Observations After the Action**: Observations about the outcomes and consequences resulting from the action.

Your goal is to produce a **factual and objective summary** that:
1. Focuses solely on the action and its direct consequences.
2. Describes the connections between the observations made before the action and the outcomes observed after the action.
3. Avoids subjective interpretations, hypothetical scenarios, or speculative reflections.

The summary must adhere to the facts presented in the observations and avoid introducing external perspectives, philosophical musings, or subjective conclusions.

---

# Contextual Information

## Character Summary

{character_summary}

## Chapter Summary

{chapter_summary}

## Context

{context}

---

# Observations Before the Action

{obss_before}

---

# Action

{act}

---

# Observations After the Action

{obss_after}

---

# Expected Summary

"""
