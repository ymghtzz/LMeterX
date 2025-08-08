ANALYSIS_PROMPT = """
    Analyze the LLM stress test configuration: {test_config} and performance results: {results}, then produce a concise, technical evaluation focused on the metrics below.

    Rules
    - First_token_latency assessment: Good (<1.00s), Moderate (1.00–2.00s), Poor (>2.00s).
    - Total_time assessment: Good (<60.00s), Moderate (60.00–180.00s), Poor (>180.00s).
   -  if Total_time is Poor, highlight how First_token_latency, Total_tps, and Avg_total_tokens influence Total_time.
    - failure_request: If there is a failed request, please indicate it in the `Identified Issues` and direct the user to check the task log for the specific error information.
    - If a metric is missing, display N/A (do not infer).
    - Keep output under 300 words, technical, and prioritize the most severe issues.

    Required Output Format
    ### Performance Summary
    [1–3 sentence overall assessment, including UX judgment and the dominant bottleneck(s).]

    ### Key Metrics
    | Metric | Value(avg/max) | Threshold/Target | Verdict |
    |---|---|---|---|
    | Concurrent_users | N | — | — |
    | First_token_latency(s) | X.XX | Good (<1.00s), Moderate (1.00–2.00s), Poor (>2.00s) | Good/Moderate/Poor |
    | Total_time(s) | X.XX | Good (<60.00s), Moderate (60.00–180.00s), Poor (>180.00s) | Good/Moderate/Poor |
    | RPS(req/s) | X.XX | — | — |
    | Completion_tps(tokens/s) | X.XX | — | — |
    | Total_tps(tokens/s) | X.XX | — | — |
    | Avg_completion_tokens(tokens/req) | N | — | — |
    | Avg_total_tokens(tokens/req) | N | — | — |
    |Failure_request| N | — | — |

    ### Identified Issues
    1. [Most critical issue with metric value and impact, if any]
    2. [Highlight failure_request, if any]
    """
