ANALYSIS_PROMPT_EN = """
    Analyze the LLM stress test configuration: {test_config} and performance results: {results}, then produce a concise, technical evaluation focused on the metrics below.

    Rules:
    - First_token_latency assessment: Good (<1.00s), Moderate (1.00–2.00s), Poor (>2.00s).
    - Total_time assessment: Good (<60.00s), Moderate (60.00–180.00s), Poor (>180.00s).
   -  if Total_time is Poor, highlight how First_token_latency, Total_tps, and Avg_total_tokens influence Total_time.
    - failure_request: If there is a failed request, please indicate it in the `Identified Issues` and direct the user to check the task log for the specific error information.
    - If a metric is missing, display N/A (do not infer).
    - Keep output under 300 words, technical, and prioritize the most severe issues.

    Required Output Format:
    ### Performance Summary
    [1–3 sentence overall assessment, including UX judgment and the dominant bottleneck(s).]

    ### Key Metrics
    | Metric | Value(avg/max) | Threshold/Target | Verdict |
    |---|---|---|---|
    | Concurrent_users | N | — | — |
    | First_token_latency(s) | X.XX | Good (<1.00s), Moderate (1.00–2.00s), Poor (>2.00s) | Good/Moderate/Poor |
    | Total_time(s) | X.XX | Good (<60.00s), Moderate (60.00–180.00s), Poor (>180.00s) | Good/Moderate/Poor |
    | RPS(req/s) | X.XX | — | — |
    | Completion Tps(Tokens/s) | X.XX | — | — |
    | Total Tps(Tokens/s) | X.XX | — | — |
    | Avg_completion_tokens(Tokens/req) | N | — | — |
    | Avg_total_tokens(Tokens/req) | N | — | — |
    |Failure_request| N | — | — |

    ### Identified Issues
    1. [Most critical issue with metric value and impact, if any]
    2. [Highlight failure_request, if any]
    """

ANALYSIS_PROMPT_CN = """
    请分析 LLM 压测配置：{test_config} 和性能结果：{results}，然后针对以下指标和要求生成一份简明的技术评估报告。

    规则：
    - First_token_latency 评估：良好（<1.00 秒），中等（1.00-2.00 秒），较差（>2.00 秒）。
    - Total_time 评估：良好（<60.00 秒），中等（60.00-180.00 秒），较差（>180.00 秒）。
    - 如果 Total_time 为“较差”，请重点说明和分析 First_token_latency、Total_tps 和 Avg_total_tokens 对 Total_time 的影响。
    - Failure_request：如果存在失败的请求，请在“已识别问题”中指出。
    - 如果缺少某个指标，则显示 N/A（不推断）。
    - 输出内容应控制在 300 字以内，技术性强，并优先处理最严重的问题。

    输出格式要求：
    ### 性能总结
    [1-3 句总体评估，包括用户体验判断和主要瓶颈。]

    ### 关键指标
    | 指标 | 值（平均值/最大值） | 阈值/目标 | 结论 |
    |---|---|---|---|
    | 并发用户数 | N | — | — |
    | 首Token时延 (s) | X.XX | 良好 (<1.00 秒)、中等 (1.00-2.00 秒)、较差 (>2.00 秒) | 良好/中等/较差 |
    | 总时间 (s) | X.XX | 良好 (<60.00 秒)、中等 (60.00-180.00 秒)、较差 (>180.00 秒) | 良好/中等/较差 |
    | RPS（请求/秒）| X.XX | — | — |
    | Completion Tokens 吞吐量（Tokens/秒）| X.XX | — | — |
    | Total Tokens 吞吐量（Tokens/秒）| X.XX | — | — |
    | 平均每请求输出Token数量（Tokens/请求）| N | — | — |
    | 平均每请求总Token数量（Tokens/请求）| N | — | — |
    | 失败请求| N | — | — |

    ### 已识别的问题
    1. [具有指标值和影响的最关键问题（如果有）]
    2. [重点说明是否存在失败请求，并指引用户查看任务日志以获取具体的错误信息（如果有）]
    """


def get_analysis_prompt(language: str = "en") -> str:
    """
    根据语言获取相应的分析提示词

    Args:
        language: 语言代码，支持 'en'（英文）和 'zh'（中文）

    Returns:
        str: 相应语言的分析提示词
    """
    if language == "zh":
        return ANALYSIS_PROMPT_CN
    else:
        return ANALYSIS_PROMPT_EN
