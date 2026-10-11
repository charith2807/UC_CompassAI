"""Build the human-review workbook and the retrieval charts from saved results.

Reads:  eval/golden.jsonl, eval/results/{B0,B1,B2,B3}.dev.jsonl (answer runs)
        eval/results/{B1,B2,A3-rerank,B3}.dev.retrieval.jsonl (retrieval-only runs, latency in ms)
Writes: eval/Human_Review.xlsx  (gold verification + failure labelling)
        reports/figures/recall_at_5_dev.png, reports/figures/answer_correct_dev.png
Run:    python -m eval.report_artifacts
"""
import json
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from eval.run_eval import RESULTS, load_golden, percentile

ROOT = RESULTS.parent.parent
FIG_DIR = ROOT / "reports" / "figures"
XLSX = RESULTS.parent / "Human_Review.xlsx"
CHAIN = ["B0", "B1", "B2", "A1-structure", "A2-hybrid", "A3-rerank", "A4-expand", "B3"]
TODAY = date.today().isoformat()

# Chart styling (dataviz reference palette: blue slot, light surface, ink tokens)
BLUE, SURFACE, INK, INK_2, GRID = "#2a78d6", "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"

ANSWER_CONFIGS = [("B0", "B0 Closed-book"), ("B1", "B1 BM25"), ("B2", "B2 Dense (naive chunks)"),
                  ("B3", "B3 Final (hybrid + rerank)")]
RETRIEVAL_CONFIGS = [("B1", "B1 BM25"), ("B2", "B2 Dense"), ("A3-rerank", "Hybrid + reranker"),
                     ("B3", "B3 Hybrid + reranker + rewrite fallback")]
FAILURE_LABELS = ["retrieval miss", "rank failure", "chunk boundary", "extraction failure", "stale content",
                  "reranker demotion", "generator ignored context", "invalid citation", "over-refusal",
                  "hallucination", "not a failure (scorer error)"]


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in open(RESULTS / name)]


def avg(rs: list[dict], key: str) -> float | None:
    vals = [r["scores"][key] for r in rs if key in r["scores"]]
    return sum(vals) / len(vals) if vals else None


# ---------------------------------------------------------------- metrics
def retrieval_table() -> list[tuple[str, list]]:
    data = {c: rows(f"{c}.dev.retrieval.jsonl") for c, _ in RETRIEVAL_CONFIGS}
    answerable = {c: [r for r in rs if r["expected"] == "answer"] for c, rs in data.items()}
    table = []
    for label, key in [("Recall@5", "recall@5"), ("Recall@20", "recall@20"), ("MRR", "mrr"), ("nDCG@10", "ndcg@10")]:
        table.append((label, [avg(answerable[c], key) for c, _ in RETRIEVAL_CONFIGS]))
    for label, p in [("p50 latency (ms)", 50), ("p95 latency (ms)", 95)]:
        table.append((label, [1000 * percentile([r["latency_s"] for r in data[c]], p) for c, _ in RETRIEVAL_CONFIGS]))
    return table


def answer_table() -> list[tuple[str, list]]:
    data = {c: rows(f"{c}.dev.jsonl") for c, _ in ANSWER_CONFIGS}
    ans = {c: [r for r in rs if r["expected"] == "answer"] for c, rs in data.items()}
    non = {c: [r for r in rs if r["expected"] != "answer"] for c, rs in data.items()}
    lat = {c: [r["latency_s"] for r in rs] for c, rs in data.items()}
    return [
        ("Answer correct (answerable)", [avg(ans[c], "correct") for c, _ in ANSWER_CONFIGS]),
        ("Citation valid", [avg(ans[c], "citation_valid") for c, _ in ANSWER_CONFIGS]),
        ("Over-refusal (answerable)", [avg(ans[c], "false_refusal") for c, _ in ANSWER_CONFIGS]),
        ("Correct refusal/referral (unanswerable)", [avg(non[c], "correct") for c, _ in ANSWER_CONFIGS]),
        ("p50 end-to-end latency (s)", [percentile(lat[c], 50) for c, _ in ANSWER_CONFIGS]),
        ("p95 end-to-end latency (s)", [percentile(lat[c], 95) for c, _ in ANSWER_CONFIGS]),
        ("Cost per query ($)", [sum(r["cost_usd"] for r in data[c]) / len(data[c]) for c, _ in ANSWER_CONFIGS]),
    ]


# ---------------------------------------------------------------- charts
def bar_chart(labels: list[str], values: list[float], title: str, subtitle: str, path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    bars = ax.bar(range(len(values)), values, width=0.5, color=BLUE, zorder=3)
    for b, v in zip(bars, values):  # value labels: few bars, so every bar is labelled
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.0%}", ha="center", va="bottom",
                fontsize=10, color=INK, fontweight="bold")
    ax.set_xticks(range(len(labels)), labels, fontsize=9, color=INK_2)
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0], ["0%", "25%", "50%", "75%", "100%"], fontsize=9, color=INK_2)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0)
    fig.text(0.02, 0.95, title, fontsize=13, fontweight="bold", color=INK, ha="left")
    fig.text(0.02, 0.89, subtitle, fontsize=9, color=INK_2, ha="left")
    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.08, right=0.98)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- workbook
ARIAL = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3A5F")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")  # cells the reviewer fills in
AUTO_FILL = PatternFill("solid", fgColor="EEF3F8")
THIN = Border(bottom=Side(style="thin", color="D9D9D9"))


def header(ws, cols: list[tuple[str, int]], row: int = 1) -> None:
    for i, (name, width) in enumerate(cols, start=1):
        c = ws.cell(row=row, column=i, value=name)
        c.font = Font(name=ARIAL, bold=True, color="FFFFFF", size=10)
        c.fill = HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[row].height = 32


def body_font(ws) -> None:
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if c.font is None or not c.font.bold:
                c.font = Font(name=ARIAL, size=10, color=c.font.color.rgb if c.font and c.font.color and c.font.color.type == "rgb" else None)
            c.alignment = Alignment(wrap_text=True, vertical="top")


def build_workbook(golden: dict, retrieval: list, answers: list) -> None:
    """Only the human work the course requires: verify every gold answer (all 50 items)
    and label >= 15 failures. Per-answer scoring is automatic (eval/run_eval.py)."""
    from eval.failures import suggest
    wb = Workbook()

    # --- Gold Verification: every golden item, dev and test
    gv = wb.active
    gv.title = "Gold Verification"
    header(gv, [("Question ID", 10), ("Split", 7), ("Category", 13), ("Question", 42), ("Gold answer", 44),
                ("Source URL(s)", 38), ("Evidence quote (<= 25 words) / what was searched", 44),
                ("Verified against the page? Y/N", 13), ("Corrected gold answer (only if N)", 30),
                ("Human reviewer", 16), ("Reviewed date UTC", 13), ("Comments", 34)])
    r = 2
    for g in golden.values():
        urls = "\n".join(u for u in [g.get("source_url", ""), *g.get("also_valid_urls", [])] if u)
        evidence = g.get("evidence_quote") or ("Searched: " + g["searched"] if g.get("searched") else "")
        vals = [g["id"], g["split"], g["type"], g["question"], g["gold_answer"], urls, evidence]
        for col, v in enumerate(vals, start=1):
            gv.cell(row=r, column=col, value=v)
        for col in range(8, 13):
            gv.cell(row=r, column=col).fill = INPUT_FILL
        gv.cell(row=r, column=11).number_format = "yyyy-mm-dd"
        r += 1
    last_gv = r - 1
    dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
    dv.add(f"H2:H{last_gv}")
    gv.add_data_validation(dv)
    gv.freeze_panes = "E2"
    gv.auto_filter.ref = f"A1:L{last_gv}"
    body_font(gv)

    # --- Error Analysis: every failure candidate, dev and test; label at least 15
    ea = wb.create_sheet("Error Analysis")
    header(ea, [("Question ID", 10), ("Split", 7), ("Baseline", 13), ("Category", 13), ("Question", 40),
                ("Gold answer", 34), ("Bot answer", 55), ("Suggested label (script)", 24),
                ("Human label", 24), ("Human reviewer", 16), ("Notes", 36)])
    er = 2
    for split in ("dev", "test"):
        for c in CHAIN:
            path = RESULTS / f"{c}.{split}.jsonl"
            if not path.exists():
                continue
            for res in map(json.loads, open(path)):
                if res["scores"].get("correct", 1.0) == 0.0:
                    g = golden[res["id"]]
                    vals = [res["id"], split, c, g["type"], g["question"], g["gold_answer"], res["answer"][:800],
                            suggest(g, res).split(" (")[0]]
                    for col, v in enumerate(vals, start=1):
                        ea.cell(row=er, column=col, value=v)
                    for col in range(9, 12):
                        ea.cell(row=er, column=col).fill = INPUT_FILL
                    er += 1
    last_ea = er - 1
    dv = DataValidation(type="list", formula1='"' + ",".join(FAILURE_LABELS) + '"', allow_blank=True)
    dv.add(f"I2:I{max(last_ea, 2)}")
    ea.add_data_validation(dv)
    ea.freeze_panes = "F2"
    ea.auto_filter.ref = f"A1:K{last_ea}"
    body_font(ea)

    # --- Instructions
    ins = wb.create_sheet("Instructions")
    ins.column_dimensions["A"].width = 28
    ins.column_dimensions["B"].width = 100
    lines = [
        ("What this workbook is for", "The two human tasks the MSAI 633 rubric requires: (1) verify every gold "
                                      "answer against its page (all 50 items, dev and test); (2) hand-label at least "
                                      "15 failures. Per-answer scores are computed automatically by eval/run_eval.py."),
        ("Which cells to edit", "Only the yellow cells: 'Gold Verification' columns H-L and 'Error Analysis' "
                                "columns I-K. Everything else is generated; don't edit it."),
        ("Gold Verification", "Open the source URL, find the evidence quote, and check the gold answer. "
                              "Y = correct as written. N = wrong or incomplete: write the corrected answer. For "
                              "unanswerable items, confirm the information really isn't on the site (the "
                              "'searched' note lists what was checked)."),
        ("Error Analysis", f"{last_ea - 1} failure candidates from all baselines and ablation steps. Label at "
                           f"least 15 (pick ones you can explain). The suggested label is a guess from the trace; "
                           f"read the bot answer and choose the human label from the list."),
        ("Failure categories", "retrieval miss · rank failure · chunk boundary · extraction failure · stale "
                               "content · reranker demotion · generator ignored context · invalid citation · "
                               "over-refusal · hallucination · not a failure (scorer error)"),
        ("Example: Gold Verification", "s01 | Y | (blank) | Karthik L. | 2026-10-10 | 'Online undergraduate is "
                                       "$220 per credit hour.' found on the Financial Aid FAQ page."),
        ("Example: Error Analysis", "m03 | test | A2-hybrid | Human label: rank failure | Notes: right page ranked "
                                    "#1 but the 5 chunks sent were other rows of the equivalency table."),
        ("After review", "If any gold answer is corrected, update eval/golden.jsonl and re-score without new "
                         "API calls: python -m eval.run_eval --configs ... --split dev --rescore (and test)."),
        ("Source of data", f"eval/golden.jsonl; eval/results/*.dev.jsonl and *.test.jsonl. Built {TODAY} by "
                           f"python -m eval.report_artifacts."),
    ]
    for i, (k, v) in enumerate(lines, start=1):
        ins.cell(row=i, column=1, value=k).font = Font(name=ARIAL, bold=True, size=10)
        ins.cell(row=i, column=2, value=v).font = Font(name=ARIAL, size=10)
        ins.cell(row=i, column=2).alignment = Alignment(wrap_text=True, vertical="top")

    # --- Progress: live formulas
    pr = wb.create_sheet("Progress")
    header(pr, [("Task", 34), ("Required", 10), ("Done", 10), ("Remaining", 11), ("Status", 14)])
    tasks = [
        ("Gold answers verified (Y or N)", f"=COUNTA('Gold Verification'!$A$2:$A${last_gv})",
         f"=COUNTA('Gold Verification'!$H$2:$H${last_gv})"),
        ("Gold answers marked N (need correction)", "-", f'=COUNTIF(\'Gold Verification\'!$H$2:$H${last_gv},"N")'),
        ("Failures hand-labelled", 15, f"=COUNTA('Error Analysis'!$I$2:$I${max(last_ea, 2)})"),
    ]
    for i, (name, req, done) in enumerate(tasks, start=2):
        pr.cell(row=i, column=1, value=name)
        pr.cell(row=i, column=2, value=req)
        pr.cell(row=i, column=3, value=done)
        if req != "-":
            pr.cell(row=i, column=4, value=f"=MAX(B{i}-C{i},0)")
            pr.cell(row=i, column=5, value=f'=IF(C{i}>=B{i},"done","in progress")')
    body_font(pr)

    # --- Results (values computed by this script from saved runs; no human input)
    rs = wb.create_sheet("Results")
    rs.column_dimensions["A"].width = 38
    rs.cell(row=1, column=1, value="Actual retrieval results - source-URL retrieval evaluation - development set only")
    header(rs, [("Metric", 38)] + [(lbl, 22) for _, lbl in RETRIEVAL_CONFIGS], row=3)
    for i, (metric, vals) in enumerate(retrieval, start=4):
        rs.cell(row=i, column=1, value=metric)
        for j, v in enumerate(vals, start=2):
            cell = rs.cell(row=i, column=j, value=round(v, 4) if v is not None else "-")
            cell.number_format = "0.0" if "ms" in metric else "0.00%" if "Recall" in metric else "0.0000"
    start = 4 + len(retrieval) + 2
    rs.cell(row=start - 1, column=1, value="Answer-level results - development set only (n = 22 answerable, 11 unanswerable/refer)")
    header(rs, [("Metric", 38)] + [(lbl, 22) for _, lbl in ANSWER_CONFIGS], row=start)
    for i, (metric, vals) in enumerate(answers, start=start + 1):
        rs.cell(row=i, column=1, value=metric)
        for j, v in enumerate(vals, start=2):
            cell = rs.cell(row=i, column=j, value=round(v, 5) if v is not None else "-")
            cell.number_format = "0.00" if "latency" in metric else "$0.0000" if "Cost" in metric else "0.0%"
    note = start + len(answers) + 2
    rs.cell(row=note, column=1, value=(
        "Source: eval/results/*.dev.retrieval.jsonl (retrieval-only runs: latency = retrieval + rerank, no LLM "
        "answer) and eval/results/*.dev.jsonl (full runs with Claude Haiku 5.5). Recall/MRR/nDCG are page-level "
        "over answerable items with a gold URL. Built by python -m eval.report_artifacts."))
    rs.cell(row=note, column=1).alignment = Alignment(wrap_text=True)
    rs.merge_cells(start_row=note, start_column=1, end_row=note, end_column=5)
    rs.row_dimensions[note].height = 48
    body_font(rs)
    for row in (1, start - 1):
        rs.cell(row=row, column=1).font = Font(name=ARIAL, bold=True, size=12)

    wb.save(XLSX)


def main() -> None:
    golden = {g["id"]: g for g in load_golden()}
    retrieval, answers = retrieval_table(), answer_table()
    bar_chart([lbl.replace(" + reranker + rewrite fallback", "\n+ reranker + rewrite") for _, lbl in RETRIEVAL_CONFIGS],
              retrieval[0][1], "Recall@5 comparison",
              "Share of answerable dev questions whose gold page is in the top 5 (n = 21)",
              FIG_DIR / "recall_at_5_dev.png")
    bar_chart([lbl.replace(" (", "\n(") for _, lbl in ANSWER_CONFIGS], answers[0][1], "Answer correctness",
              "Share of answerable dev questions answered correctly (n = 22)", FIG_DIR / "answer_correct_dev.png")
    build_workbook(golden, retrieval, answers)
    print("retrieval (dev):")
    for metric, vals in retrieval:
        print(f"  {metric:20} " + "  ".join(f"{v:9.4f}" if v is not None else "        -" for v in vals))
    print(f"wrote {XLSX.relative_to(ROOT)}, {FIG_DIR.relative_to(ROOT)}/recall_at_5_dev.png, answer_correct_dev.png")


if __name__ == "__main__":
    main()
