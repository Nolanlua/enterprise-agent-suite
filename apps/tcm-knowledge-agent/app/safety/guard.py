"""Rule-first safety guard.

A medical knowledge agent must fail closed on emergencies and prescription
requests. Rules are intentionally simple, auditable and independent of the LLM;
the model is not trusted to decide whether it should refuse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SafetyDecision:
    level: str
    reasons: list[str] = field(default_factory=list)
    disclaimer: str = (
        "以上内容仅用于中医药知识检索和学习，不构成诊断、处方或用药建议；"
        "具体诊疗请由执业中医师或药师面诊后决定。"
    )


EMERGENCY_PATTERNS = [
    r"胸痛|胸闷伴大汗|呼吸困难|意识不清|昏迷|抽搐|大出血|休克|口唇发紫",
    r"自杀|轻生|不想活",
]
PRESCRIPTION_PATTERNS = [
    r"给我开(一)?(张|个|副)?方|开点药|直接开药|帮我配药|处方",
    r"剂量|吃多少|一天吃几克|加量|减量",
]
SPECIAL_POPULATION_PATTERNS = [
    r"孕妇|怀孕|哺乳|备孕",
    r"儿童|小孩|婴儿|宝宝",
    r"肝肾功能|透析|化疗|术后",
]
SELF_HARM_PATTERNS = [r"附子.*(自己|自行|大量|长期)", r"麻黄.*(自己|自行|大量|长期)"]


class SafetyGuard:
    def evaluate(self, question: str, intent: str = "") -> SafetyDecision:
        reasons: list[str] = []
        if any(re.search(pattern, question) for pattern in EMERGENCY_PATTERNS):
            return SafetyDecision(
                level="emergency",
                reasons=["emergency_symptom"],
                disclaimer="出现急危重症表现，请立即拨打 120 或前往最近医院急诊，不要依赖在线问答。",
            )
        if any(re.search(pattern, question) for pattern in PRESCRIPTION_PATTERNS):
            reasons.append("prescription_or_dosage_request")
        if any(re.search(pattern, question) for pattern in SPECIAL_POPULATION_PATTERNS):
            reasons.append("special_population")
        if any(re.search(pattern, question) for pattern in SELF_HARM_PATTERNS):
            reasons.append("self_medication_risk")
        if reasons:
            return SafetyDecision(level="block", reasons=reasons)
        return SafetyDecision(level="pass")

    def inspect_answer(self, answer: str) -> list[str]:
        forbidden = [
            r"包治百病",
            r"保证治愈",
            r"绝对安全",
            r"无需就医",
            r"自行加大剂量",
            r"可以长期服用",
        ]
        return [pattern for pattern in forbidden if re.search(pattern, answer)]
