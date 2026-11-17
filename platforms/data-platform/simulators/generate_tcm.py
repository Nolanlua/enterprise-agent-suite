"""Generate a small, deterministic TCM corpus for local development.

The corpus is synthetic and must not be treated as medical advice. It mimics the
shape of real data: classics, herbs, formulas and clinical guidelines, with
source, dynasty, contraindications and version metadata.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "raw" / "tcm"
OUT.mkdir(parents=True, exist_ok=True)

CATEGORIES = ["classic", "herb", "formula", "guideline"]
HERBS = [
    ("黄芪", "补气升阳，固表止汗", "阴虚阳亢者慎用"),
    ("当归", "补血活血，调经止痛", "湿盛中满、大便溏泄者慎用"),
    ("麻黄", "发汗解表，宣肺平喘", "高血压、心脏病患者慎用"),
    ("附子", "回阳救逆，温阳散寒", "孕妇禁用；需先煎、久煎"),
    ("黄连", "清热燥湿，泻火解毒", "脾胃虚寒者慎用"),
    ("甘草", "补脾益气，调和诸药", "不宜与甘遂、大戟同用"),
]
FORMULAS = [
    ("四君子汤", "人参、白术、茯苓、甘草", "脾胃气虚证"),
    ("四物汤", "熟地黄、当归、白芍、川芎", "营血虚滞证"),
    ("麻黄汤", "麻黄、桂枝、杏仁、甘草", "外感风寒表实证"),
    ("六味地黄丸", "熟地黄、山茱萸、山药、泽泻、牡丹皮、茯苓", "肾阴亏虚证"),
]
CLASSICS = [
    ("黄帝内经", "先秦"),
    ("伤寒论", "东汉"),
    ("金匮要略", "东汉"),
    ("本草纲目", "明"),
]
GUIDELINES = ["中医内科常见病诊疗指南", "中成药临床应用指导原则", "中药学本科规划教材"]


def stable_id(value: str) -> str:
    return "tcm_" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def build_documents() -> list[dict]:
    rng = random.Random(20261117)
    docs: list[dict] = []
    for herb, effect, caution in HERBS:
        content = (
            f"{herb}，性味归经见药典。主要功效：{effect}。临床用于相关证候的配伍治疗。"
            f"使用注意：{caution}。具体剂量、煎服方法与配伍禁忌应由执业中医师根据患者情况决定。"
            "本文仅用于知识检索演示，不构成诊疗建议。"
        )
        docs.append(
            {
                "doc_id": stable_id("herb:" + herb),
                "title": f"中药条目：{herb}",
                "category": "herb",
                "source": "中国药典（模拟整理）",
                "dynasty": "现代",
                "content": content,
                "herbs": [herb],
                "formulas": [],
                "contraindications": [caution],
            }
        )
    for name, composition, indication in FORMULAS:
        content = (
            f"{name}，组成：{composition}。功用主治：{indication}。"
            "方剂的使用需要辨证论治，并根据患者体质、合并用药和禁忌进行调整。"
            "本方仅用于知识库检索演示，不构成处方建议。"
        )
        docs.append(
            {
                "doc_id": stable_id("formula:" + name),
                "title": f"方剂条目：{name}",
                "category": "formula",
                "source": "方剂学（模拟整理）",
                "dynasty": "现代",
                "content": content,
                "herbs": [item for item in composition.replace("、", " ").split()],
                "formulas": [name],
                "contraindications": ["孕妇及特殊人群需遵医嘱"],
            }
        )
    for title, dynasty in CLASSICS:
        content = (
            f"《{title}》是中医经典著作，成书于{dynasty}。其理论体系强调阴阳五行、脏腑经络、"
            "辨证论治和整体观念。学习时应结合原文上下文、历代注家和现代教材，不可断章取义。"
            "本条为模拟摘要，用于检索评测，不替代原文和权威校注本。"
        )
        docs.append(
            {
                "doc_id": stable_id("classic:" + title),
                "title": f"经典导读：{title}",
                "category": "classic",
                "source": title,
                "dynasty": dynasty,
                "content": content,
                "herbs": [],
                "formulas": [],
                "contraindications": [],
            }
        )
    for index, guideline in enumerate(GUIDELINES):
        content = (
            f"{guideline}强调辨证与辨病结合、个体化治疗和安全用药。对于特殊人群、妊娠、肝肾功能异常、"
            "合并用药等情况，应先评估风险。知识库回答必须给出处，并提示由执业医师复核。"
            "本段为模拟文本，用于流程演示。"
        )
        docs.append(
            {
                "doc_id": stable_id(f"guideline:{index}"),
                "title": f"指南摘要：{guideline}",
                "category": "guideline",
                "source": guideline,
                "dynasty": "现代",
                "content": content,
                "herbs": [],
                "formulas": [],
                "contraindications": ["特殊人群需遵医嘱"],
            }
        )
    # A few hard negatives help the eval set detect over-answer behavior.
    docs.append(
        {
            "doc_id": stable_id("negative:no_evidence"),
            "title": "知识库边界说明",
            "category": "guideline",
            "source": "平台治理规范",
            "dynasty": "现代",
            "content": "知识库不提供在线诊断、处方开具和剂量调整。遇到急危重症、妊娠、儿童、肝肾功能异常等情况，"
            "应转交线下医疗机构。对于知识库没有收录的问题，应明确说不知道，不得编造经典原文。"
            "本条为安全边界说明，属于平台治理文档。",
            "herbs": [],
            "formulas": [],
            "contraindications": ["不提供诊断和处方"],
        }
    )
    rng.shuffle(docs)
    return docs


def main() -> None:
    docs = build_documents()
    path = OUT / "documents.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")
    herbs = [{"name": name, "effect": effect, "caution": caution} for name, effect, caution in HERBS]
    (OUT / "herbs.json").write_text(json.dumps(herbs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(docs)} TCM documents to {path}")


if __name__ == "__main__":
    main()
