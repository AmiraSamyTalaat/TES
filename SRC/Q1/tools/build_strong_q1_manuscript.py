from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, RGBColor
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_BREAK

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "publication" / "PROVLAB_COMPLETE_MANUSCRIPT_Q1_SUBMISSION_READY.docx"
OUTDIR = ROOT / "publication" / "strong_q1"
OUTDIR.mkdir(parents=True, exist_ok=True)
EXT = ROOT / "outputs" / "strong_q1_extension"

CLEAN_OUT = OUTDIR / "PROVLAB_STRONG_Q1_TECHNICAL_MANUSCRIPT_CLEAN_V1_1_0.docx"
REVIEW_OUT = OUTDIR / "PROVLAB_STRONG_Q1_TECHNICAL_MANUSCRIPT_REVIEW_HIGHLIGHTED_V1_1_0.docx"

BLACK = RGBColor(0, 0, 0)
YELLOW = "yellow"
FONT = "Times New Roman"


def set_cell_shading(cell, fill="FFFFFF"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcPr.append(shd)
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")


def set_cell_border(cell, **kwargs):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.first_child_found_in("w:tcBorders")
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        if edge in kwargs:
            tag = "w:" + edge
            element = tcBorders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcBorders.append(element)
            for key, value in kwargs[edge].items():
                element.set(qn("w:" + key), str(value))


def set_repeat_table_header(row):
    trPr = row._tr.get_or_add_trPr()
    tblHeader = OxmlElement("w:tblHeader")
    tblHeader.set(qn("w:val"), "true")
    trPr.append(tblHeader)


def set_run(run, *, bold=None, italic=None, size=None, color=BLACK, highlight=False):
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.color.rgb = color
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if size is not None:
        run.font.size = Pt(size)
    if highlight:
        run.font.highlight_color = 7  # WD_COLOR_INDEX.YELLOW


def clear_paragraph(paragraph):
    p = paragraph._p
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)


def set_para_text(paragraph, text: str, *, bold_prefix: str | None = None, review=False,
                  alignment=None, size=None, bold=False, italic=False):
    clear_paragraph(paragraph)
    if alignment is not None:
        paragraph.alignment = alignment
    if bold_prefix and text.startswith(bold_prefix):
        r1 = paragraph.add_run(bold_prefix)
        set_run(r1, bold=True, size=size, highlight=review)
        r2 = paragraph.add_run(text[len(bold_prefix):])
        set_run(r2, bold=bold, italic=italic, size=size, highlight=review)
    else:
        r = paragraph.add_run(text)
        set_run(r, bold=bold, italic=italic, size=size, highlight=review)
    return paragraph


def style_paragraph(paragraph, size=11):
    for run in paragraph.runs:
        set_run(run, size=size)
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.line_spacing = 1.08


def find_para(doc: Document, starts: str):
    for p in doc.paragraphs:
        if p.text.strip().startswith(starts):
            return p
    raise KeyError(starts)


def insert_paragraph_before(anchor, text="", style=None, review=False, bold=False, italic=False,
                            alignment=None, size=11):
    new_p = OxmlElement("w:p")
    anchor._p.addprevious(new_p)
    p = anchor._parent.add_paragraph()  # create wrapper, then swap underlying element
    p._p.getparent().remove(p._p)
    p._p = new_p
    p._element = new_p
    if style:
        p.style = style
    if alignment is not None:
        p.alignment = alignment
    if text:
        r = p.add_run(text)
        effective_bold = True if style and str(style).startswith("Heading") else bold
        set_run(r, bold=effective_bold, italic=italic, size=size, highlight=review)
    return p


def insert_paragraph_after(anchor, text="", style=None, review=False, bold=False, italic=False,
                           alignment=None, size=11):
    new_p = OxmlElement("w:p")
    anchor._p.addnext(new_p)
    p = anchor._parent.add_paragraph()
    p._p.getparent().remove(p._p)
    p._p = new_p
    p._element = new_p
    if style:
        p.style = style
    if alignment is not None:
        p.alignment = alignment
    if text:
        r = p.add_run(text)
        effective_bold = True if style and str(style).startswith("Heading") else bold
        set_run(r, bold=effective_bold, italic=italic, size=size, highlight=review)
    return p


def insert_table_before(doc: Document, anchor, rows: list[list[str]], widths=None, review=False,
                        bold_cells: set[tuple[int,int]] | None = None, font_size=8.7):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    if widths:
        for ci, width in enumerate(widths):
            if ci < len(table.columns):
                table.columns[ci].width = Inches(width)
    anchor._p.addprevious(table._tbl)
    bold_cells = bold_cells or set()
    for ri, row in enumerate(rows):
        for ci, value in enumerate(row):
            cell = table.cell(ri, ci)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ci else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(value))
            set_run(r, bold=(ri == 0 or (ri,ci) in bold_cells), size=font_size, highlight=review)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_shading(cell, "FFFFFF")
            set_cell_border(cell,
                            top={"val":"single","sz":"5","color":"000000"},
                            bottom={"val":"single","sz":"5","color":"000000"},
                            left={"val":"single","sz":"5","color":"000000"},
                            right={"val":"single","sz":"5","color":"000000"})
            if widths and ci < len(widths):
                cell.width = Inches(widths[ci])
    set_repeat_table_header(table.rows[0])
    return table


def insert_math_before(anchor, equation: str, review=False):
    # Use a centered, editable text equation rather than an image. This renders
    # consistently in Word and LibreOffice while remaining fully editable.
    new_p = OxmlElement("w:p")
    anchor._p.addprevious(new_p)
    p = anchor._parent.add_paragraph()
    p._p.getparent().remove(p._p)
    p._p = new_p
    p._element = new_p
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(equation)
    set_run(r, italic=True, size=10.5, highlight=review)
    return p


def normalize_document_styles(doc: Document):
    sec = doc.sections[0]
    sec.top_margin = Inches(0.72)
    sec.bottom_margin = Inches(0.72)
    sec.left_margin = Inches(0.78)
    sec.right_margin = Inches(0.78)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = BLACK
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.08

    for sty_name, size in [("Heading 1", 14), ("Heading 2", 11.5), ("List Bullet", 10.5), ("List Number", 9.5)]:
        s = doc.styles[sty_name]
        s.font.name = FONT
        s._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        s.font.size = Pt(size)
        s.font.color.rgb = BLACK
        if "Heading" in sty_name:
            s.font.bold = True
            s.paragraph_format.space_before = Pt(8)
            s.paragraph_format.space_after = Pt(4)

    for p in doc.paragraphs:
        # Title/subtitle handled later; references smaller.
        size = 9.3 if p.style.name == "List Number" else 10.5
        for run in p.runs:
            set_run(run, size=size)
    for table in doc.tables:
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for ri, row in enumerate(table.rows):
            if ri == 0:
                set_repeat_table_header(row)
            for cell in row.cells:
                set_cell_shading(cell, "FFFFFF")
                set_cell_border(cell,
                                top={"val":"single","sz":"5","color":"000000"},
                                bottom={"val":"single","sz":"5","color":"000000"},
                                left={"val":"single","sz":"5","color":"000000"},
                                right={"val":"single","sz":"5","color":"000000"})
                for p in cell.paragraphs:
                    for r in p.runs:
                        set_run(r, size=8.7, bold=(ri == 0))


def bold_table_cell(table, row, col):
    for p in table.cell(row,col).paragraphs:
        for r in p.runs:
            r.bold = True


def format_existing_tables(doc: Document):
    # Table 2: bold strongest C-index within the same stage where multiple models are compared.
    if len(doc.tables) >= 2:
        t = doc.tables[1]
        for rc in [(3,2), (4,2), (6,2), (7,2), (8,2)]:
            # Rows: XGB-AFT validation, Full AFT audit, confirmation, stress, XGB-Cox external.
            if rc[0] < len(t.rows):
                bold_table_cell(t,*rc)
    if len(doc.tables) >= 3:
        t = doc.tables[2]
        for r in range(1,len(t.rows)):
            bold_table_cell(t,r,4)  # XGB-Cox C exceeds Cox C in every subgroup.


def add_algorithm_table(doc: Document, anchor, review=False):
    rows = [
        ["Step", "Operation"],
        ["Input", "For each candidate feature j and selection cycle c, compute mean absolute SHAP magnitude M(j,c) and the Spearman correlation d(j,c) between feature value and SHAP contribution."],
        ["1", "Normalize within each cycle: I(j,c) = M(j,c) / sum over features of M(.,c)."],
        ["2", "Compute mean importance Ī(j) and temporal coefficient of variation CV(j)."],
        ["3", "Retain direction evidence where |d(j,c)| >= 0.10 and compute direction agreement A(j); use A(j)=0.5 when no cycle meets the reliability threshold."],
        ["4", "Compute TES(j) = Ī(j) × A(j) / [1 + CV(j)] and rank features in descending order."],
        ["5", "Select the smallest ranked panel whose cumulative TES mass reaches 0.90, constrained to 8-15 variables; force age and sex if absent."],
        ["Output", "Return the selected panel. In this study, 2009-2010 and 2011-2012 were the selection cycles; 2013-2014 was reserved as the independent audit and 2015-2018 was not used for selection."],
    ]
    table = insert_table_before(doc, anchor, rows, widths=[0.75, 6.85], review=review, font_size=8.5)
    return table


def load_metrics():
    status = json.loads((EXT / "STRONG_Q1_EXTENSION_STATUS.json").read_text(encoding="utf-8"))
    with open(EXT / "SURVIVAL_METRICS_CENSORING_AWARE.csv", newline="", encoding="utf-8") as f:
        metrics = list(csv.DictReader(f))
    return status, metrics


def build(review=False):
    doc = Document(ORIGINAL)
    normalize_document_styles(doc)
    format_existing_tables(doc)

    # -------------------------- Title / abstract --------------------------
    title = doc.paragraphs[0]
    set_para_text(title,
        "Temporal Explanation-Stable Feature Selection for Parsimonious Survival Machine Learning: Frozen Chronological and External Era Validation",
        review=review, alignment=WD_ALIGN_PARAGRAPH.CENTER, size=17, bold=True)
    subtitle = doc.paragraphs[1]
    set_para_text(subtitle,
        "A survey-aware NHANES study with a reproducible 11-variable panel and no-refit external testing",
        review=review, alignment=WD_ALIGN_PARAGRAPH.CENTER, size=11.5, italic=True)

    set_para_text(find_para(doc,"Background:"),
        "Background: Temporal dataset shift can make random-split performance an optimistic proxy for deployment-era generalization. We developed a reproducible survival-learning framework that combines chronological freezing with Temporal Explanation-Stable (TES) feature selection to test whether a compact laboratory panel can retain transportable discrimination.",
        bold_prefix="Background: ", review=review)
    set_para_text(find_para(doc,"Methods:"),
        "Methods: Adults from NHANES 1999-2018 were linked to public-use mortality outcomes. Models were developed on 1999-2008, evaluated on 2009-2012, audited on 2013-2014, and tested under frozen protocols in 2015-2018. Cox, XGBoost-Cox, and XGBoost accelerated failure-time (AFT) models were compared with participant-paired bootstrap confidence intervals. TES ranks variables by normalized SHAP importance penalized for temporal magnitude variation and weighted by feature-effect direction agreement; the smallest panel reaching 90% TES-score mass was retained. No-refit evaluation was performed in independently harmonized NHANES III. Explicitly separated post-hoc analyses compared TES with feature-selection baselines and added Uno's C, cumulative/dynamic AUC, IPCW Brier score, and calibration sensitivity.",
        bold_prefix="Methods: ", review=review)
    set_para_text(find_para(doc,"Results:"),
        "Results: The contemporary cohort included 52,287 adults and 8,311 deaths. In 2009-2012, XGBoost-Cox exceeded Cox (C-index 0.8608 vs 0.8486; difference 0.0122, 95% CI 0.0093-0.0149), and AFT added a smaller gain (0.00135, 95% CI 0.00020-0.00250). TES selected 11 of 25 variables; removing either temporal-stability component under the same 90% mass rule produced a 12-variable panel. TES-11 was noninferior to full AFT in the 2013-2014 audit and in NHANES III, where its C-index was 0.8494. Mean-SHAP mass selection required 12 variables for essentially the same external discrimination, while univariate Cox top-11 reached 0.8455. Censoring-aware sensitivity preserved strong TES discrimination (24-month Uno's C 0.8752 in validation, 0.8851 in frozen confirmation, and 0.8668 externally).",
        bold_prefix="Results: ", review=review)
    set_para_text(find_para(doc,"Conclusions:"),
        "Conclusions: TES provides a formal, explanation-stability-aware route to predictor reduction within a chronologically frozen survival-learning workflow. The 11-variable panel preserved nearly all full-model discrimination across later cycles and a substantially earlier external survey era, while component ablation, alternative selection baselines, censoring-aware metrics, protocol freezes, and executable verification strengthen the technical evidence for transportability and reproducibility.",
        bold_prefix="Conclusions: ", review=review)
    set_para_text(find_para(doc,"Keywords:"),
        "Keywords: survival analysis; temporal dataset shift; feature selection; NHANES; XGBoost; accelerated failure time; SHAP; Uno's C; transportability; reproducibility",
        bold_prefix="Keywords: ", review=review)

    # --------------------------- Introduction ----------------------------
    set_para_text(find_para(doc,"Clinical risk-prediction models are commonly"),
        "Clinical risk-prediction models are often evaluated with random train-test splits. Although convenient, random splitting mixes calendar eras and can conceal changes in measurement practice, population composition, follow-up, and predictor-outcome relationships. Temporal dataset shift is a recognized challenge in health machine learning, and empirical studies show that clinically relevant model behavior can change across time even when the prediction task appears unchanged [16-20,27]. For time-to-event outcomes, transportability assessment must additionally respect right censoring and separate rank discrimination from horizon-specific probability accuracy [10-12].",
        review=review)
    set_para_text(find_para(doc,"Machine-learning survival models can represent"),
        "Survival prediction has expanded from semiparametric Cox regression to nonlinear approaches including random survival forests, boosted-tree objectives, and deep survival models [3-5,13-15]. These methods can capture interactions and nonlinear predictor-response structure, but greater flexibility increases the importance of validation that preserves chronology and keeps confirmatory data sealed from model selection. TRIPOD+AI and PROBAST+AI similarly emphasize transparent model evaluation, representative validation, and explicit analysis choices [8,9].",
        review=review)
    set_para_text(find_para(doc,"Explainability introduces an additional"),
        "Explainability introduces a second transportability problem: a model may preserve overall discrimination while changing which predictors drive its outputs. SHAP provides local and global decompositions of tree-model predictions [6,7], and survival-specific approaches such as SurvSHAP(t) extend explanation to time-to-event outputs [21]. Separately, feature-selection research has established that stability of selected variables is itself a methodological property rather than a cosmetic reporting choice [22,23]. The present study connects these lines by using cross-cycle explanation stability as an explicit feature-selection signal and then auditing the resulting sparse survival model across later and external eras.",
        review=review)

    # Related work: replace two existing paras and add one.
    rw1 = find_para(doc,"Survival prediction has progressed")
    set_para_text(rw1,
        "Nonlinear survival learning has been developed through ensemble trees, neural Cox formulations, competing-risk networks, and gradient boosting [5,13-15]. Their methodological gains are usually assessed through discrimination and prediction-error measures, for which censoring-aware estimators such as Uno's C, cumulative/dynamic AUC, and IPCW Brier scores provide complementary views [11,24-26]. In contrast to a leaderboard-oriented comparison across many learners, our focus is the transportability of a fixed survival-learning pipeline under calendar-time separation and predictor reduction.",
        review=review)
    rw2 = find_para(doc,"The unresolved methodological gap")
    set_para_text(rw2,
        "Temporal shift has received increasing attention in clinical machine learning. Prior work has formalized shift-stable modeling, reviewed mitigation strategies, benchmarked domain generalization/adaptation, documented large-scale temporal shifts in healthcare tasks, and evaluated feature-selection strategies under temporal change [16-20,27]. These studies establish that recalibration, retraining, domain adaptation, and feature-level interventions can matter, but they also show that no single mitigation strategy reliably protects all aspects of performance. A complementary question is therefore whether a model can be selected, frozen, and evaluated prospectively across later eras without adapting to each target period.",
        review=review)
    rw3 = insert_paragraph_after(rw2,
        "Explanation stability and selection stability provide a mechanism for addressing that question at the predictor level. SHAP-based survival explanation can reveal variable contributions [6,7,21], while stability-selection literature quantifies robustness of selected feature sets under data perturbation [22,23]. The methodological opportunity addressed here is to integrate temporal explanation magnitude, temporal variability, and direction consistency into a parsimonious selection rule, then couple that rule to independent audit, prespecified noninferiority, frozen chronological confirmation, and no-refit external-era evaluation. This differs from selecting features solely by a single-cycle importance ranking or by conventional univariate association.",
        review=review)

    obj = find_para(doc,"We evaluated whether nonlinear survival learning")
    set_para_text(obj,
        "We evaluated whether nonlinear survival learning trained on NHANES 1999-2008 maintained performance across later cycles and NHANES III, whether an AFT objective added useful discrimination, and whether Temporal Explanation-Stable (TES) selection could produce a smaller panel without materially sacrificing performance. The study makes six technical contributions:",
        review=review)
    bullets = [p for p in doc.paragraphs if p.style.name == "List Bullet" and p.text.strip()][:5]
    contribution_texts = [
        "Formal Temporal Explanation-Stable selection. TES converts cycle-specific SHAP magnitude, temporal coefficient of variation, and feature-effect direction agreement into an explicit score and a reproducible 90%-mass panel-selection rule.",
        "Chronologically frozen evaluation. Development, selection/validation, audit, confirmation, short-follow-up stress testing, and external-era evaluation are separated in calendar order, with confirmatory outcomes sealed before use.",
        "Censoring-aware comparative inference. Cox, XGBoost-Cox, and XGBoost-AFT are compared with participant-paired bootstrap confidence intervals; additional Uno's C, cumulative/dynamic AUC, and IPCW Brier analyses test metric robustness.",
        "Parsimonious noninferiority with ablation and selection baselines. TES-11 reduces the 25-variable panel by 56%, is tested against full AFT with a fixed C-index margin, and is challenged against component ablations and alternative feature-ranking strategies.",
        "Temporal explanation auditing. Global SHAP rankings, magnitudes, top-feature overlap, and feature-effect direction reversals are quantified across cycles rather than summarized from a single explanation snapshot.",
    ]
    for p,txt in zip(bullets, contribution_texts):
        set_para_text(p, txt, review=review)
    # Insert sixth contribution before Methods.
    methods_h = find_para(doc,"2. Methods")
    insert_paragraph_before(methods_h,
        "Transportability and reproducibility controls. The workflow combines subgroup and survey-weight sensitivity analyses, no-refit NHANES III evaluation, source-data reconstruction, executable code, protocol freezes, model/configuration hashes, and machine-readable verification.",
        style="List Bullet", review=review)

    # ------------------------------- Methods -----------------------------
    models_p = find_para(doc,"TES-11 was derived using Temporal")
    set_para_text(models_p,
        "TES-11 was derived from the AFT learner using the frozen feature-selection protocol described below. Feature selection used SHAP profiles from 2009-2010 and 2011-2012; 2013-2014 was reserved for the independent development audit. Neither 2015-2018 confirmatory/stress outcomes nor NHANES III outcomes were used to choose the TES panel.",
        review=review)

    eval_h = find_para(doc,"2.4 Evaluation and statistical analysis")
    # Insert TES formal section immediately before former 2.4.
    tes_h = insert_paragraph_before(eval_h,"2.4 Temporal Explanation-Stable (TES) feature selection",style="Heading 2",review=review,size=11.5)
    tes_intro = insert_paragraph_before(eval_h,
        "For feature j in selection cycle c, let M(j,c) denote mean absolute SHAP magnitude and let I(j,c)=M(j,c) divided by the sum of M(l,c) over all candidate features l be its within-cycle normalized importance. Let d(j,c) be Spearman's rho between the observed feature value and its SHAP contribution. The frozen TES rule is formalized as follows, with C selection cycles and ε>0 used only to avoid division by zero:",
        review=review)
    insert_math_before(eval_h,"Ī(j) = (1/C) × Σ[c=1…C] I(j,c)",review=review)
    insert_math_before(eval_h,"CV(j) = √{(1/C) × Σ[c=1…C] [I(j,c) − Ī(j)]²} / max[Ī(j), ε]",review=review)
    insert_math_before(eval_h,"R(j) = {c: |d(j,c)| ≥ 0.10};  A(j) = |mean of sign[d(j,c)] over c in R(j)|; if R(j) is empty, A(j) = 0.5",review=review)
    insert_math_before(eval_h,"TES(j) = Ī(j) × A(j) / [1 + CV(j)]",review=review)
    insert_math_before(eval_h,"K* = smallest K with cumulative TES-score mass ≥ 0.90; 8 ≤ K ≤ 15; age and sex are forced",review=review)
    insert_paragraph_before(eval_h,
        "The denominator penalizes features whose global SHAP magnitude varies across the selection cycles, while A(j) discounts features whose reliable SHAP direction is inconsistent. The final rule is deterministic once the cycle-specific SHAP profiles are fixed. Recomputing these equations from the frozen profiles reproduced the exact TES-11 panel byte-for-byte at the feature-list level.",
        review=review)
    alg_cap = insert_paragraph_before(eval_h,"Algorithm 1. Temporal Explanation-Stable (TES) feature selection",review=review,bold=True,size=9.5)
    add_algorithm_table(doc, eval_h, review=review)

    # Renumber existing methods headings.
    set_para_text(eval_h,"2.5 Evaluation and statistical analysis",review=review,bold=True,size=11.5)
    set_para_text(find_para(doc,"2.5 Temporal explainability analysis"),"2.6 Temporal explainability analysis",review=review,bold=True,size=11.5)
    repro_h = find_para(doc,"2.6 Reproducibility and claim control")
    # Add post-hoc robustness section before reproducibility.
    post_h = insert_paragraph_before(repro_h,"2.7 Post-hoc technical robustness analyses",style="Heading 2",review=review,size=11.5)
    insert_paragraph_before(repro_h,
        "To strengthen methodological interpretation without altering any frozen success gate, we performed an explicitly separated post-hoc extension. First, TES component ablation recomputed the original 90% mass rule under four scores: importance only; importance with the temporal-CV penalty but without direction agreement; importance with direction agreement but without the CV penalty; and the full TES score. Second, fixed-hyperparameter AFT models were trained for alternative feature-selection baselines: mean-SHAP mass, latest-cycle SHAP mass, XGBoost gain top-11, and standardized univariate Cox top-11. All baseline selection and tuning used only development/selection data; NHANES III outcomes were never used for feature selection or tuning.",
        review=review)
    insert_paragraph_before(repro_h,
        "Third, censoring-aware sensitivity analyses were calculated at 24 months in every evaluation stage and at 60 months where follow-up support was adequate. Uno's concordance used inverse-probability-of-censoring weights [11]; cumulative/dynamic AUC followed the incident-information framework for censored outcomes [24]; and prediction error was quantified by IPCW Brier score and integrated Brier score [25,26]. The censoring distribution and Cox baseline hazards were estimated from the 1999-2008 development cohort. Horizon-specific IPCW calibration intercept and slope were retained as exploratory probability-calibration diagnostics rather than confirmatory gates. These analyses are additional sensitivity analyses and do not retroactively redefine the frozen confirmatory protocol.",
        review=review)
    set_para_text(repro_h,"2.8 Reproducibility and claim control",review=review,bold=True,size=11.5)
    repro_p = find_para(doc,"The analysis retained protocol-freeze files")
    set_para_text(repro_p,
        "The analysis retained protocol-freeze files, model and configuration hashes, machine-readable status reports, explicit progression gates, source-data checksums, and a reviewer-ready reproduction workflow. The Strong-Q1 extension writes all ablation, baseline-selection, censoring-aware metric, and calibration outputs to a separate results namespace and records that frozen confirmatory artifacts were not modified. Public-use source data and script-based reconstruction support computational reproducibility subject to source-data access terms.",
        review=review)

    # ------------------------------- Results -----------------------------
    # Update 3.4 text and add component ablation after existing predictor table.
    tes_res = find_para(doc,"TES-11 reduced the full 25-variable")
    set_para_text(tes_res,
        "TES-11 reduced the full 25-variable predictor panel to 11 variables, a 56% reduction. In the 2013-2014 audit, TES-11 achieved C=0.8583 compared with 0.8591 for full AFT (difference -0.00077, 95% CI -0.00286 to 0.00129). In NHANES III, TES-11 achieved C=0.8494 compared with 0.8508 for full AFT (difference -0.00144, 95% CI -0.00221 to -0.00068). Both differences were within the prespecified noninferiority margin of -0.005. Recalculation of the formal TES equations reproduced the frozen 11-variable panel exactly.",
        review=review)

    external_h = find_para(doc,"3.5 External-era transportability")
    # Insert Table 5 before new 3.5 heading.
    insert_paragraph_before(external_h,"Table 5. TES component ablation under the original 90% score-mass rule",review=review,bold=True,size=9.5)
    ab_rows = [
        ["Selection score", "Temporal-CV penalty", "Direction term", "Predictors", "Reduction vs 25"],
        ["Importance only", "No", "No", "12", "52%"],
        ["No direction term", "Yes", "No", "12", "52%"],
        ["No CV penalty", "No", "Yes", "12", "52%"],
        ["Full TES", "Yes", "Yes", "11", "56%"],
    ]
    insert_table_before(doc, external_h, ab_rows, widths=[2.1,1.25,1.15,0.9,1.2], review=review,
                        bold_cells={(4,3),(4,4)},font_size=8.5)
    insert_paragraph_before(external_h,
        "Under the identical 90% cumulative-mass rule, importance alone and either single temporal component selected 12 variables, whereas the full TES score selected 11. The extra parsimony resulted from the joint temporal penalty and direction-consistency weighting; the ablation is therefore interpreted as evidence about the selection rule, not as proof that either component independently increases discrimination.",
        review=review)

    # New feature-selection baseline section before external.
    insert_paragraph_before(external_h,"3.5 Feature-selection baseline comparison",style="Heading 2",review=review,size=11.5)
    insert_paragraph_before(external_h,
        "Alternative selection rules produced similar or larger panels but different audit/external behavior. Mean-SHAP mass required 12 variables and closely matched TES externally (C=0.84937 vs 0.84939) while using one additional predictor. Latest-cycle SHAP achieved the highest audit C-index (0.85852) but a lower external C-index (0.84858). XGBoost gain top-11 was nearly identical to TES externally but lower in the independent audit (0.85390), and univariate Cox top-11 was lower in both audit (0.85165) and external evaluation (0.84549). These results position TES as a competitive, more explicitly temporally constrained selector rather than a relabeling of a single SHAP ranking.",
        review=review)
    insert_paragraph_before(external_h,"Table 6. Post-hoc feature-selection baseline comparison using fixed AFT training policy",review=review,bold=True,size=9.5)
    baseline_rows = [
        ["Selection method", "Predictors", "2013-2014 audit C", "NHANES III external C"],
        ["TES", "11", "0.858289", "0.849387"],
        ["Mean-SHAP mass", "12", "0.857945", "0.849372"],
        ["Latest-cycle SHAP mass", "12", "0.858523", "0.848580"],
        ["XGBoost gain top-11", "11", "0.853895", "0.849395"],
        ["Univariate Cox top-11", "11", "0.851647", "0.845487"],
    ]
    insert_table_before(doc, external_h, baseline_rows, widths=[2.6,1.0,1.5,1.6], review=review,
                        bold_cells={(3,2),(4,3)},font_size=8.5)
    # Renumber external and temporal SHAP.
    set_para_text(external_h,"3.6 External-era transportability",review=review,bold=True,size=11.5)
    shap_h = find_para(doc,"3.6 Temporal SHAP stability")
    set_para_text(shap_h,"3.7 Temporal SHAP stability",review=review,bold=True,size=11.5)
    set_para_text(find_para(doc,"Table 5. Pairwise temporal stability"),
                  "Table 7. Pairwise temporal stability of global SHAP explanations",review=review,bold=True,size=9.5)

    # Add censoring-aware section before Discussion, after figure 3.
    discussion_h = find_para(doc,"4. Discussion")
    insert_paragraph_before(discussion_h,"3.8 Censoring-aware survival sensitivity",style="Heading 2",review=review,size=11.5)
    insert_paragraph_before(discussion_h,
        "Censoring-aware sensitivity analyses supported the main discrimination narrative across all chronological stages. At 24 months, TES-11 Uno's C was 0.8752 in 2009-2012 validation, 0.8626 in the 2013-2014 audit, 0.8851 in frozen 2015-2016 confirmation, 0.8631 in the 2017-2018 stress cohort, and 0.8668 in NHANES III. Corresponding cumulative/dynamic AUC values were 0.8745, 0.8603, 0.8926, 0.8650, and 0.8711. The pattern was consistent with the original Harrell C analyses and showed that the principal rank-discrimination conclusions were not dependent on a single concordance estimator.",
        review=review)
    insert_paragraph_before(discussion_h,
        "At 24 months, TES-11 IPCW Brier scores ranged from 0.0176 to 0.0251 across the five evaluation cohorts. Integrated Brier scores were 0.0245 over 6-60 months in validation, 0.0257 in the audit, 0.0190 over 6-48 months in frozen confirmation, 0.0144 over 6-24 months in the short-follow-up stress cohort, and 0.0346 over 6-60 months in NHANES III. Exploratory calibration diagnostics were less stable than discrimination for AFT probability estimates, so the technical claim remains transportable risk ranking and parsimonious discrimination rather than universally calibrated absolute risk.",
        review=review)
    insert_paragraph_before(discussion_h,"Table 8. Censoring-aware sensitivity for TES-11 AFT",review=review,bold=True,size=9.5)
    sens_rows = [
        ["Evaluation cohort", "Uno C, 24 mo", "AUC, 24 mo", "IPCW Brier, 24 mo", "Integrated Brier (range)"],
        ["2009-2012 validation", "0.8752", "0.8745", "0.0176", "0.0245 (6-60 mo)"],
        ["2013-2014 audit", "0.8626", "0.8603", "0.0190", "0.0257 (6-60 mo)"],
        ["2015-2016 frozen confirmation", "0.8851", "0.8926", "0.0180", "0.0190 (6-48 mo)"],
        ["2017-2018 stress", "0.8631", "0.8650", "0.0183", "0.0144 (6-24 mo)"],
        ["NHANES III external", "0.8668", "0.8711", "0.0251", "0.0346 (6-60 mo)"],
    ]
    insert_table_before(doc, discussion_h, sens_rows, widths=[2.35,1.0,1.0,1.25,1.65], review=review,font_size=8.3)

    # ------------------------------ Discussion --------------------------
    intro_disc = find_para(doc,"This study provides evidence that nonlinear")
    set_para_text(intro_disc,
        "This study shows that nonlinear survival learning based on routine laboratory measurements can maintain strong rank discrimination across later NHANES cycles and a substantially earlier external survey era. Three findings organize the contribution. First, XGBoost-Cox consistently improved discrimination over a full-panel Cox baseline under chronological testing. Second, the AFT objective produced an additional validation gain while remaining externally comparable to Cox-objective boosting. Third, the formally specified TES rule reduced 25 predictors to 11 while preserving near-full-panel performance internally and externally, and post-hoc technical analyses showed that this parsimony was not reproduced by the same 90% mass rule when either temporal-stability component was removed.",
        review=review)
    tech = find_para(doc,"The central technical contribution is an integrated")
    set_para_text(tech,
        "The central technical contribution is the coupling of a formal temporal explanation-stability selector with a frozen transportability-evaluation architecture. TES is not simply top-k SHAP: it normalizes global SHAP importance by cycle, penalizes temporal variation in magnitude, weights reliable feature-effect direction agreement, and chooses the smallest panel meeting a fixed cumulative-score criterion. The method is then challenged outside the selection cycles through an independent audit, prespecified noninferiority, frozen temporal confirmation, short-follow-up stress testing, and no-refit NHANES III evaluation. This turns parsimony into a testable transportability property rather than a retrospective preference for fewer variables.",
        review=review)
    aft_disc = find_para(doc,"The AFT objective added a complementary")
    set_para_text(aft_disc,
        "The component ablation clarifies what the temporal terms add. With the original 90% mass threshold and identical minimum/maximum panel constraints, importance-only selection and either one-component temporal variant retained 12 variables, whereas full TES retained 11. The feature-selection baselines provide a second challenge: mean-SHAP required 12 variables for essentially the same external C-index, latest-cycle SHAP traded slightly higher audit performance for lower external performance, and conventional gain/univariate rankings showed less consistent audit performance. The appropriate interpretation is not universal superiority of TES, but evidence that explicit temporal explanation constraints can achieve competitive transportability with a smaller, reproducible panel.",
        review=review)
    # Insert censoring-aware interpretation after AFT disc.
    insert_paragraph_after(aft_disc,
        "The expanded survival evaluation also reduces dependence on Harrell's C. Uno's C and cumulative/dynamic AUC preserved the same broad discrimination pattern at 24 months, including frozen and external testing, while IPCW Brier analyses quantified prediction error over supported horizons. Probability-calibration diagnostics were more sensitive to era and model objective than rank discrimination, reinforcing a useful separation: the present framework provides strong evidence for transportable ranking, whereas calibrated absolute-risk deployment remains a distinct prospective step.",
        review=review)

    # Rename later headings and strengthen.
    set_para_text(find_para(doc,"4.2 Clinical and operational relevance"),"4.2 Clinical and operational relevance",review=False,bold=True,size=11.5)
    clin = find_para(doc,"TES-11 is operationally attractive")
    set_para_text(clin,
        "TES-11 is operationally attractive because it uses age, sex, and nine routinely available analytes while preserving C-index within 0.002 of full AFT externally. The 56% panel reduction lowers measurement and data-completeness burden and provides a compact candidate risk-ranking model for prospective calibration, decision-curve analysis, and implementation studies. Its value in this study is therefore both methodological and operational: a transparent selection rule produced a small panel that remained competitive across multiple calendar eras without external refitting.",
        review=review)
    expl = find_para(doc,"The temporal SHAP results show")
    set_para_text(expl,
        "The temporal SHAP results show that the model relied on a stable predictor hierarchy across adjacent cycles. Near-perfect rank correlations, complete top-10 overlap, small magnitude divergence, and few direction reversals provide convergent evidence that performance was not driven by a transient feature ordering. TES uses this temporal explanation information constructively at selection time, while the separate three-cycle SHAP audit evaluates whether explanation structure remains stable beyond the two selection cycles. This extends explainability from a descriptive snapshot to a reproducible component of model selection and transportability auditing.",
        review=review)
    strengths = find_para(doc,"Strengths include a large population-based")
    set_para_text(strengths,
        "Strengths include a large population-based cohort, strict chronological separation, formal TES selection, independent audit, prespecified gates, participant-paired bootstrap inference, frozen external-era evaluation, component ablation, alternative selection baselines, censoring-aware sensitivity metrics, subgroup auditing, quantitative temporal explanation stability, and an executable reviewer-ready package with source reconstruction and hash verification.",
        review=review)

    # Keep scientifically necessary limitations but compress framing into one paragraph/list set.
    lim_h = find_para(doc,"4.5 Scope and limitations")
    set_para_text(lim_h,"4.5 Scope and limitations",review=False,bold=True,size=11.5)
    lims = [p for p in doc.paragraphs if p.style.name == "List Bullet" and p.text.strip().startswith(("Public-use mortality","NHANES is observational","Later cycles","Discrimination near","SHAP values"))]
    lim_texts = [
        "Public-use mortality linkage supports all-cause survival modeling but has restricted cause-specific detail.",
        "NHANES is observational and US-based; evaluation in contemporary health systems and other countries remains an important next transportability step.",
        "Later cycles have shorter administrative follow-up; 2017-2018 is therefore used as a supported-horizon stress test rather than a long-horizon absolute-risk study.",
        "The new calibration sensitivity confirms that strong discrimination should not be equated with universally calibrated absolute risk or clinical net benefit.",
        "SHAP characterizes the fitted model rather than causal effects and can reflect predictor correlation.",
    ]
    for p,txt in zip(lims,lim_texts):
        set_para_text(p,txt,review=review)
    future = find_para(doc,"The next validation phase should estimate")
    set_para_text(future,
        "The next phase should prospectively evaluate TES-11 in independent health systems and countries, recalibrate horizon-specific absolute risks where necessary, quantify net benefit with decision-curve analysis, and assess whether the explanation-stability criterion remains useful when measurement platforms or clinical workflows change. These extensions can move the compact panel from robust population risk ranking toward evaluated decision support.",
        review=review)

    concl = find_para(doc,"Explainable nonlinear survival models trained")
    set_para_text(concl,
        "Temporal Explanation-Stable selection provides a reproducible technical mechanism for reducing a survival-learning predictor panel while explicitly accounting for cross-cycle explanation magnitude and direction. In 52,287 contemporary NHANES participants, nonlinear survival learning improved discrimination over Cox; TES reduced 25 predictors to 11 and remained noninferior to full AFT in the independent audit and no-refit NHANES III evaluation. Component ablation showed that the joint temporal-stability terms were required to reach the 11-variable panel under the frozen 90% mass rule, while alternative feature-selection baselines and censoring-aware metrics supported the robustness of the transportability result. Chronological freezing, paired inference, formalized explanation-stable selection, external-era testing, and executable verification together provide a strong reproducible framework for studying parsimonious survival machine learning under temporal shift.",
        review=review)

    # ------------------------------ References ---------------------------
    refs_h = find_para(doc,"References")
    # Append references 13-27 after existing last reference.
    existing_ref_texts = [p.text.strip() for p in doc.paragraphs if p.style.name == "List Number"]
    new_refs = [
        "Ishwaran H, Kogalur UB, Blackstone EH, Lauer MS. Random survival forests. Ann Appl Stat. 2008;2(3):841-860. doi:10.1214/08-AOAS169.",
        "Katzman JL, Shaham U, Cloninger A, et al. DeepSurv: personalized treatment recommender system using a Cox proportional hazards deep neural network. BMC Med Res Methodol. 2018;18:24. doi:10.1186/s12874-018-0482-1.",
        "Lee C, Zame W, Yoon J, van der Schaar M. DeepHit: a deep learning approach to survival analysis with competing risks. Proc AAAI Conf Artif Intell. 2018;32(1). doi:10.1609/aaai.v32i1.11842.",
        "Subbaswamy A, Saria S. From development to deployment: dataset shift, causality, and shift-stable models in health AI. Biostatistics. 2020;21(2):345-352. doi:10.1093/biostatistics/kxz041.",
        "Guo LL, Pfohl SR, Fries J, et al. Systematic review of approaches to preserve machine learning performance in the presence of temporal dataset shift in clinical medicine. Appl Clin Inform. 2021;12(4):808-815. doi:10.1055/s-0041-1735184.",
        "Guo LL, Pfohl SR, Fries J, et al. Evaluation of domain generalization and adaptation on improving model robustness to temporal dataset shift in clinical medicine. Sci Rep. 2022;12:2726. doi:10.1038/s41598-022-06484-1.",
        "Ji CX, Alaa AM, Sontag D. Large-scale study of temporal shift in health insurance claims. Proc Mach Learn Res. 2023;209:243-278.",
        "Silva GFDS, Barcellos Filho FN, Wichmann RM, et al. Strategies for detecting and mitigating dataset shift in machine learning for health predictions: a systematic review. J Biomed Inform. 2025;170:104902. doi:10.1016/j.jbi.2025.104902.",
        "Krzyzinski M, Spytek M, Baniecki H, Biecek P. SurvSHAP(t): time-dependent explanations of machine learning survival models. Knowl Based Syst. 2023;262:110234. doi:10.1016/j.knosys.2022.110234.",
        "Nogueira S, Sechidis K, Brown G. On the stability of feature selection algorithms. J Mach Learn Res. 2018;18(174):1-54.",
        "Meinshausen N, Buhlmann P. Stability selection. J R Stat Soc Series B Stat Methodol. 2010;72(4):417-473. doi:10.1111/j.1467-9868.2010.00740.x.",
        "Heagerty PJ, Lumley T, Pepe MS. Time-dependent ROC curves for censored survival data and a diagnostic marker. Biometrics. 2000;56(2):337-344. doi:10.1111/j.0006-341X.2000.00337.x.",
        "Graf E, Schmoor C, Sauerbrei W, Schumacher M. Assessment and comparison of prognostic classification schemes for survival data. Stat Med. 1999;18(17-18):2529-2545. doi:10.1002/(SICI)1097-0258(19990915/30)18:17/18<2529::AID-SIM274>3.0.CO;2-5.",
        "Gerds TA, Schumacher M. Consistent estimation of the expected Brier score in general survival models with right-censored event times. Biom J. 2006;48(6):1029-1040. doi:10.1002/bimj.200610301.",
        "Lemmon J, Guo LL, Posada J, et al. Evaluation of feature selection methods for preserving machine learning performance in the presence of temporal dataset shift in clinical medicine. Methods Inf Med. 2023;62(1-2):60-70. doi:10.1055/s-0043-1762904.",
    ]
    # Add after last existing reference paragraph.
    ref_paras = [p for p in doc.paragraphs if p.style.name == "List Number"]
    last_ref = ref_paras[-1]
    for ref in new_refs:
        last_ref = insert_paragraph_after(last_ref, ref, style="List Number", review=review, size=9.3)

    # Ensure all headings/table captions/body are black and font-consistent after insertions.
    for p in doc.paragraphs:
        if p.style.name == "List Number":
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.0
        default_size = 9.3 if p.style.name == "List Number" else (8.8 if p.text.startswith("Table ") or p.text.startswith("Figure ") or p.text.startswith("Algorithm ") else 10.5)
        if p.style.name == "Heading 1": default_size = 14
        elif p.style.name == "Heading 2": default_size = 11.5
        for r in p.runs:
            # Preserve review highlights already applied.
            set_run(r, size=(r.font.size.pt if r.font.size else default_size), color=BLACK)
    # Reapply title/subtitle sizes after normalization pass.
    for r in doc.paragraphs[0].runs: set_run(r,size=17,bold=True)
    for r in doc.paragraphs[1].runs: set_run(r,size=11.5,italic=True)

    # Keep figure captions centered and black.
    for p in doc.paragraphs:
        if p.text.startswith("Figure "):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                set_run(r,size=8.7,bold=True)

    # Tables: black/white, compact, consistent font. Review highlighting for existing altered table captions only;
    # inserted tables already highlighted if review=True.
    for table in doc.tables:
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for ri,row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                set_cell_shading(cell,"FFFFFF")
                for p in cell.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT if ci == 0 else WD_ALIGN_PARAGRAPH.CENTER
                    for r in p.runs:
                        # Preserve existing highlight state.
                        set_run(r,size=(r.font.size.pt if r.font.size else 8.7),color=BLACK)

    # Update metadata without touching scientific content.
    props = doc.core_properties
    props.title = doc.paragraphs[0].text
    props.subject = "Strong-Q1 technical manuscript revision with TES formalization and post-hoc robustness analyses"
    props.keywords = "survival analysis; temporal dataset shift; TES; SHAP; NHANES; XGBoost; transportability"

    out = REVIEW_OUT if review else CLEAN_OUT
    doc.save(out)
    return out


if __name__ == "__main__":
    clean = build(review=False)
    review = build(review=True)
    print(clean)
    print(review)
