"""Script to fetch and compile authentic IPA System Architect (SA) AM2 past exam questions.

Sources authentic exam questions and detailed explanations (2021-2025, 125 questions total),
structures them into the ExamQuestion schema, and writes them to data/seeds/sa_YYYY_am2.json.
"""

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

# Ensure stdout handles UTF-8 on Windows
sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.models import AnswerKey, ExamQuestion

SEEDS_DIR = PROJECT_ROOT / "data" / "seeds"

URLS = {
    2021: ("https://masassiah.web.fc2.com/contents/23sa/am2_2021h.html", "秋期"),
    2022: ("https://masassiah.web.fc2.com/contents/23sa/am2_2022h.html", "秋期"),
    2023: ("https://masassiah.web.fc2.com/contents/23sa/am2_2023h.html", "春期"),
    2024: ("https://masassiah.web.fc2.com/contents/23sa/am2_2024h.html", "春期"),
    2025: ("https://masassiah.web.fc2.com/contents/23sa/am2_2025h.html", "春期"),
}

# Category classification mapping based on SA syllabus topics
TOPIC_CATEGORY_MAP = {
    # システムアーキテクチャ・ソフトウェア設計
    "アーキテクチャ": "システムアーキテクチャ設計",
    "デザインパターン": "ソフトウェアアーキテクチャ設計",
    "パターン": "ソフトウェアアーキテクチャ設計",
    "設計": "システムアーキテクチャ設計",
    "モデル": "ソフトウェアエンジニアリング",
    "アジャイル": "ソフトウェアエンジニアリング",
    "開発": "ソフトウェアエンジニアリング",
    "DFD": "システム要件定義",
    "UML": "ソフトウェアアーキテクチャ設計",
    "SysML": "システム要件定義",
    "アシュアランスケース": "システム要件定義",
    "テスト": "ソフトウェアエンジニアリング",
    "レビュー": "ソフトウェアエンジニアリング",
    # データベース・データ設計
    "データベース": "データベース設計",
    "SQL": "データベース設計",
    "トランザクション": "データベース設計",
    "リレーショナル": "データベース設計",
    "NoSQL": "データベース設計",
    # ネットワーク・通信
    "ネットワーク": "ネットワーク設計",
    "IP": "ネットワーク設計",
    "PBX": "ネットワーク設計",
    "プロトコル": "ネットワーク設計",
    # セキュリティ
    "セキュリティ": "情報セキュリティ",
    "暗号": "情報セキュリティ",
    "認証": "情報セキュリティ",
    "攻撃": "情報セキュリティ",
    "リスク": "情報セキュリティ",
}

SUPPLEMENTAL_EXPLANATIONS = {
    "2022-SA-AM2-Q24": (
        "トランザクションの待ちグラフ（Wait-For Graph）は、トランザクション間の資源ロック待ち依存関係を有向グラフで表現したものです。"
        "グラフの矢印 Ti → Tj は「Ti が Tj による資源のアンロックを待っている状態」を表します。\n"
        "時刻 t5 で T4 が update(B) で専有ロックを要求した際、t2, t3 で既に共有ロックを取得している T2, T3 のアンロックを待つため、T4 → T2, T4 → T3 の矢印が引かれます。\n"
        "時刻 t8 で T2 が update(C) で専有ロックを要求した際、t6 で共有ロックを取得している T1 のアンロックを待つため、T2 → T1 の矢印が引かれます。\n"
        "時刻 t9 で T3 が update(A) で専有ロックを要求した際、t1 で共有ロックを取得している T1、および t4 で共有ロックを取得している T4 のアンロックを待つため、T3 → T1, T3 → T4 の矢印が引かれます。\n"
        "したがって、T4 から待たれ、かつ自らは T1 を待っているノード a は T2 となり、正解は「イ」です。"
    )
}

def determine_category(topic: str, question_text: str) -> str:
    combined = f"{topic} {question_text}"
    for kw, cat in TOPIC_CATEGORY_MAP.items():
        if kw in combined:
            return cat
    return "システムアーキテクチャ設計"

def clean_html(text: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    def img_replace(match):
        alt = re.search(r'alt=["\'](.*?)["\']', match.group(0))
        if alt:
            return f" [図: {alt.group(1)}] "
        return " [図] "
    text = re.sub(r'<img[^>]+>', img_replace, text)
    text = re.sub(r'<table[^>]*>', '\n[表]\n', text)
    text = re.sub(r'</tr>', '\n', text)
    text = re.sub(r'<td[^>]*>', ' | ', text)
    text = re.sub(r'<th[^>]*>', ' | ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    lines = [re.sub(r'[ \t\u3000]+', ' ', line).strip() for line in text.split('\n')]
    lines = [line for line in lines if line]
    return '\n'.join(lines)

def extract_table_choices(table_html: str) -> list[dict[str, str]]:
    choices = []
    rows = re.findall(r'<tr>(.*?)</tr>', table_html, re.DOTALL)
    for row in rows:
        th_match = re.search(r'<th>.*?([アイウエ])\s*.*?</th>', row, re.DOTALL)
        if not th_match:
            th_match = re.search(r'<td>.*?([アイウエ])\s*.*?</td>', row, re.DOTALL)
        if th_match:
            key = th_match.group(1)
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            td_texts = [clean_html(td) for td in tds]
            choice_text = "、".join(td_texts)
            choices.append({"key": key, "text": choice_text})
    return choices

def parse_year_questions(year: int, url: str, term: str) -> list[dict]:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode('utf-8', errors='replace')

    js_answers = {}
    ans_obj_match = re.search(r'answers\s*=\s*\{(.*?)\}', content, re.DOTALL)
    if ans_obj_match:
        pairs = re.findall(r'q(\d+)\s*:\s*(\d+)', ans_obj_match.group(1))
        val_map = {"1": "ア", "2": "イ", "3": "ウ", "4": "エ"}
        for q_str, v_str in pairs:
            js_answers[int(q_str)] = val_map.get(v_str, "")

    questions = []
    sec_matches = re.finditer(r'<section id="no(\d+)">(.*?)</section>', content, re.DOTALL)
    for m in sec_matches:
        q_num = int(m.group(1))
        sec_html = m.group(2)

        h2_match = re.search(r'<h2>問\d+\s*(.*?)</h2>', sec_html)
        topic = h2_match.group(1).strip() if h2_match else ""

        ques_div = re.search(r'<div class="ques">(.*?)</div>\s*<div class="a_botton"', sec_html, re.DOTALL)
        if not ques_div:
            ques_div = re.search(r'<div class="ques">(.*?)</div>', sec_html, re.DOTALL)
        ques_html = ques_div.group(1) if ques_div else ""

        choices = []
        choices_ol = re.search(r'<ol class="ans_choices">(.*?)</ol>', ques_html, re.DOTALL)
        if choices_ol:
            li_items = re.findall(r'<li>(.*?)</li>', choices_ol.group(1), re.DOTALL)
            for li in li_items:
                clean_li = clean_html(li)
                choice_match = re.match(r'^([アイウエ])\s*(.*)$', clean_li, re.DOTALL)
                if choice_match:
                    choices.append({"key": choice_match.group(1), "text": choice_match.group(2).strip()})
                else:
                    for k in ["ア", "イ", "ウ", "エ"]:
                        if clean_li.startswith(k):
                            choices.append({"key": k, "text": clean_li[len(k):].strip()})
                            break
        else:
            tables = re.findall(r'<table[^>]*>(.*?)</table>', ques_html, re.DOTALL)
            for tbl in tables:
                tbl_choices = extract_table_choices(tbl)
                if len(tbl_choices) == 4:
                    choices = tbl_choices
                    break

        pure_ques_html = re.sub(r'<ol class="ans_choices">.*?</ol>', '', ques_html, flags=re.DOTALL)
        pure_ques_html = re.sub(r'<table[^>]*>.*?caption>.*?選択肢.*?/table>', '', pure_ques_html, flags=re.DOTALL)
        question_text = clean_html(pure_ques_html)

        qid = f"{year}-SA-AM2-Q{q_num:02d}"

        correct_answer = js_answers.get(q_num, "")
        if not correct_answer:
            expo_div = re.search(r'<div class="exposition"[^>]*>(.*?)</div>', sec_html, re.DOTALL)
            if expo_div:
                ans_match = re.search(r'【答え】<strong[^>]*>([アイウエ])</strong>', expo_div.group(1))
                if not ans_match:
                    ans_match = re.search(r'【答え】\s*([アイウエ])', expo_div.group(1))
                if ans_match:
                    correct_answer = ans_match.group(1)

        expo_div = re.search(r'<div class="exposition"[^>]*>(.*?)</div>', sec_html, re.DOTALL)
        expo_html = expo_div.group(1) if expo_div else ""
        expo_clean_html = re.sub(r'<h4>.*?</h4>', '', expo_html)
        expo_clean_html = re.sub(r'<p><span[^>]*></span>【答え】.*?</p>', '', expo_clean_html)
        explanation = clean_html(expo_clean_html)

        if qid in SUPPLEMENTAL_EXPLANATIONS:
            explanation = SUPPLEMENTAL_EXPLANATIONS[qid]

        category = determine_category(topic, question_text)

        keywords = []
        if topic:
            keywords.append(topic)
        words = re.findall(r'([A-Za-z0-9_\-\u30A1-\u30FA]{3,})', topic)
        for w in words:
            if w not in keywords:
                keywords.append(w)

        question_obj = {
            "id": qid,
            "exam_type": "SA",
            "year": year,
            "term": term,
            "question_number": q_num,
            "question_text": question_text,
            "choices": choices,
            "correct_answer": correct_answer,
            "category": category,
            "explanation": explanation,
            "keywords": keywords,
        }
        questions.append(question_obj)

    return questions

def main():
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    all_data = {}

    for year, (url, term) in URLS.items():
        print(f"Fetching and compiling {year} ({term})...")
        raw_questions = parse_year_questions(year, url, term)
        print(f"  Extracted {len(raw_questions)} questions.")

        validated_questions = []
        for q_data in raw_questions:
            # Validate through Pydantic domain model
            eq = ExamQuestion(
                id=q_data["id"],
                exam_type=q_data["exam_type"],
                year=q_data["year"],
                term=q_data["term"],
                question_number=q_data["question_number"],
                question_text=q_data["question_text"],
                choices=q_data["choices"],
                correct_answer=AnswerKey(q_data["correct_answer"]),
                category=q_data["category"],
                explanation=q_data["explanation"],
                keywords=q_data["keywords"],
            )
            validated_questions.append(eq.model_dump())

        assert len(validated_questions) == 25, f"{year} expected 25 questions, got {len(validated_questions)}"

        all_data[year] = validated_questions
        out_file = SEEDS_DIR / f"sa_{year}_am2.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(validated_questions, f, ensure_ascii=False, indent=2)
        print(f"  Successfully wrote {len(validated_questions)} authentic questions to {out_file.name}")

    print("\n[SUCCESS] All 5 years (125 questions) compiled, validated, and saved to data/seeds/ successfully!")

if __name__ == "__main__":
    main()
