from __future__ import annotations

"""Build Strong-Q1 manuscript V1.2.0 from the frozen manuscript plus additive analyses.

V1.2.0 adds reviewer-facing evidence for:
- resampling stability of TES feature selection (Jaccard + Nogueira);
- a generic Cox survival stability-selection comparator;
- sensitivity to TES direction-reliability and cumulative-mass thresholds;
- one-title journal formatting (subtitle removed).

It calls the V1.1 builder first, then applies only additive V1.2 edits.
"""

import json
from pathlib import Path
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

import build_strong_q1_manuscript as base

ROOT = Path(__file__).resolve().parents[1]
STAB = ROOT / "outputs" / "strong_q1_stability_extension"
OUTDIR = ROOT / "publication" / "strong_q1_v1_2"
OUTDIR.mkdir(parents=True, exist_ok=True)
CLEAN_OUT = OUTDIR / "PROVLAB_STRONG_Q1_MANUSCRIPT_CLEAN_V1_2_0.docx"
REVIEW_OUT = OUTDIR / "PROVLAB_STRONG_Q1_MANUSCRIPT_REVIEW_V1_2_0.docx"


def delete_paragraph(paragraph):
    p = paragraph._element
    p.getparent().remove(p)
    paragraph._p = paragraph._element = None


def build(review: bool = False):
    base_path = base.build(review=review)
    doc = Document(base_path)
    status = json.loads((STAB / "STRONG_Q1_STABILITY_EXTENSION_STATUS.json").read_text(encoding="utf-8"))
    stab = pd.read_csv(STAB / "PANEL_SELECTION_STABILITY_SUMMARY.csv")
    sens = pd.read_csv(STAB / "TES_HYPERPARAMETER_SENSITIVITY.csv")
    comp = pd.read_csv(STAB / "STABILITY_AWARE_BASELINE_COMPARISON.csv")

    # ---------------------------- One title ----------------------------
    base.set_para_text(
        doc.paragraphs[0],
        "Temporal Explanation-Stable Feature Selection for Parsimonious Survival Machine Learning: Frozen Chronological and No-Refit External-Era Validation",
        review=review, alignment=WD_ALIGN_PARAGRAPH.CENTER, size=16.5, bold=True,
    )
    # V1.1 used paragraph 1 as a subtitle. Strong-Q1 V1.2 uses one journal title only.
    if len(doc.paragraphs) > 1 and doc.paragraphs[1].text.strip().startswith("A survey-aware NHANES"):
        delete_paragraph(doc.paragraphs[1])

    # ---------------------------- Abstract -----------------------------
    base.set_para_text(base.find_para(doc, "Methods:"),
        "Methods: Adults from NHANES 1999-2018 were linked to public-use mortality outcomes. Models were developed on 1999-2008, evaluated on 2009-2012, audited on 2013-2014, and tested under frozen protocols in 2015-2018. Cox, XGBoost-Cox, and XGBoost accelerated failure-time (AFT) models were compared with participant-paired bootstrap confidence intervals. TES combines normalized SHAP importance, a temporal coefficient-of-variation penalty, and reliable feature-effect direction agreement, then retains the smallest panel reaching 90% TES-score mass. No-refit evaluation used independently harmonized NHANES III. Separated post-hoc analyses added component ablation, alternative selectors, censoring-aware metrics, 200 stratified half-sample stability resamples, Nogueira/Jaccard stability, a Cox survival stability-selection comparator, and TES threshold sensitivity.",
        bold_prefix="Methods: ", review=review)
    base.set_para_text(base.find_para(doc, "Results:"),
        "Results: The contemporary cohort included 52,287 adults and 8,311 deaths. XGBoost-Cox exceeded Cox in 2009-2012 (C-index 0.8608 vs 0.8486; paired difference 0.0122, 95% CI 0.0093-0.0149), and AFT added a smaller gain. TES selected 11 of 25 variables and remained noninferior to full AFT in the independent audit and NHANES III (external C=0.8494). Under resampling, TES showed high panel stability (mean pairwise Jaccard 0.960; Nogueira stability 0.962), while a Cox stability-selection consensus top-11 achieved lower audit and external C-indices (0.8549 and 0.8472). The primary TES-11 panel was unchanged across direction-reliability thresholds 0.05-0.15; increasing the score-mass threshold from 90% to 92.5% and 95% produced nested 13- and 15-variable panels with only small discrimination changes. Censoring-aware sensitivity preserved strong TES discrimination across frozen and external evaluation.",
        bold_prefix="Results: ", review=review)
    base.set_para_text(base.find_para(doc, "Conclusions:"),
        "Conclusions: TES provides a formal, explanation-stability-aware route to predictor reduction within a chronologically frozen survival-learning workflow. The 11-variable panel preserved near-full-model discrimination across later cycles and a substantially earlier external survey era. Component ablation, high resampling stability, threshold robustness, a survival-specific stability-selection comparator, censoring-aware metrics, protocol freezes, and executable verification strengthen the evidence that TES is a reproducible temporally constrained selector rather than a single-cycle SHAP ranking.",
        bold_prefix="Conclusions: ", review=review)

    # ------------------------ Contributions / gap ----------------------
    gap = base.find_para(doc, "Explanation stability and selection stability provide")
    base.set_para_text(gap,
        "Explanation stability and selection stability provide complementary mechanisms for predictor robustness. SHAP-based survival explanation quantifies model reliance [6,7,21], Nogueira et al. formalize data-perturbation stability of selected feature sets [22], and stability selection uses subsampling plus recurrence to identify robust structure [23]. Temporal-shift studies have also shown that feature-level interventions can preserve performance in some clinical tasks [27]. The methodological opportunity addressed here is different: TES makes cross-cycle explanation magnitude, temporal variability, and direction consistency part of the selection score itself, then subjects the resulting sparse panel to independent audit, resampling stability analysis, threshold sensitivity, frozen chronological confirmation, and no-refit external-era evaluation.",
        review=review)

    contrib = base.find_para(doc, "Parsimonious noninferiority with ablation and selection baselines")
    base.set_para_text(contrib,
        "Parsimonious noninferiority with ablation, resampling stability, and competing selectors. TES-11 reduces the 25-variable panel by 56%, is tested against full AFT with a fixed C-index margin, is challenged against component/feature-ranking ablations and a survival-specific stability-selection consensus comparator, and is audited with Jaccard and Nogueira stability across 200 half-samples.",
        review=review)

    # ----------------------------- Methods -----------------------------
    post_h = base.find_para(doc, "2.7 Post-hoc technical robustness analyses")
    base.set_para_text(post_h, "2.7 Post-hoc technical robustness, stability, and sensitivity analyses",
                       review=review, bold=True, size=11.5)
    post_p = base.find_para(doc, "To strengthen methodological interpretation without altering")
    base.set_para_text(post_p,
        "To strengthen methodological interpretation without altering any frozen success gate, we performed an explicitly separated post-hoc extension. Component ablation recomputed the original 90% mass rule after removing temporal terms, while fixed-hyperparameter AFT models challenged TES against mean-SHAP mass, latest-cycle SHAP mass, XGBoost-gain top-11, and standardized univariate Cox top-11. Censoring-aware sensitivity added Uno's C, cumulative/dynamic AUC, IPCW Brier score, integrated Brier score, and exploratory horizon-specific calibration diagnostics. All feature selection and tuning were completed without using 2015-2018 confirmatory/stress outcomes or NHANES III outcomes.",
        review=review)
    repro_h = base.find_para(doc, "2.8 Reproducibility and claim control")
    base.insert_paragraph_before(repro_h,
        "Selection stability was evaluated in 200 stratified half-samples drawn without replacement within each TES selection cycle (2009-2010 and 2011-2012; fixed seed 20260830). For each resample, cycle-specific SHAP magnitudes and feature-SHAP direction correlations were recomputed and the complete TES rule was rerun. We report feature-selection frequencies, mean pairwise Jaccard similarity, Jaccard similarity to the frozen TES-11 panel, and the chance-corrected Nogueira stability estimator [22]. Mean-SHAP mass, latest-cycle SHAP mass, and a survival-specific Cox-score top-11 base selector were evaluated under the same resampling scheme.",
        review=review)
    base.insert_paragraph_before(repro_h,
        "As a stability-aware conceptual comparator, we applied the generic stability-selection principle of subsampling plus recurrence [23] to a Cox survival-association base selector: each half-sample selected the 11 variables with the strongest absolute standardized Cox score statistics (age and sex forced), and the consensus panel comprised the most frequently recurrent variables. We do not claim the original stability-selection false-discovery bounds for this top-k base selector. A second descriptive resampling-consensus SHAP top-11 comparator was constructed from recurrence frequencies. Both consensus panels were fixed before NHANES III outcomes were read.",
        review=review)
    base.insert_paragraph_before(repro_h,
        "TES parameter sensitivity crossed direction-reliability thresholds |rho|>=0.05, 0.10, and 0.15 with cumulative TES-score mass thresholds of 90%, 92.5%, and 95%, retaining the original 8-15 variable bounds. The unconstrained primary 90% solution was also recorded to determine whether the minimum/maximum panel limits actively determined TES-11. Unique sensitivity panels were refit under the same frozen AFT training policy and evaluated in the 2013-2014 audit and NHANES III only after selection was complete.",
        review=review)

    # ----------------------------- Results -----------------------------
    # Start Results on a fresh page so Table 1 is not split across pages.
    base.find_para(doc, "3. Results").paragraph_format.page_break_before = True
    external_h = base.find_para(doc, "3.6 External-era transportability")
    # New section before current 3.6.
    base.insert_paragraph_before(external_h, "3.6 Panel-selection stability and TES parameter sensitivity",
                                 style="Heading 2", review=review, size=11.5)

    tes_row = stab.loc[stab["selector"].eq("TES 90%-mass")].iloc[0]
    mean_row = stab.loc[stab["selector"].eq("Mean-SHAP 90%-mass")].iloc[0]
    cox_row = stab.loc[stab["selector"].eq("Cox-score top-11 base selector")].iloc[0]
    base.insert_paragraph_before(external_h,
        f"Across 200 stratified half-samples, TES remained highly stable: the mean selected panel size was {tes_row.mean_selected_count:.2f} variables, mean pairwise Jaccard similarity was {tes_row.mean_pairwise_jaccard:.3f}, Nogueira stability was {tes_row.nogueira_stability:.3f}, and mean Jaccard similarity to the frozen TES-11 panel was {tes_row.mean_jaccard_to_frozen_tes11:.3f}. The 11 frozen TES variables were selected in every resample, while creatinine was the only additional variable with material recurrence (61.5%), explaining why resampled panel size varied between 11 and 12. Mean-SHAP mass was perfectly stable in these data but consistently retained 12 variables, illustrating that set stability alone does not establish the same parsimony target.",
        review=review)

    stability_rows = [
        ["Selector", "Mean K", "Mean Jaccard", "Nogueira", "Jaccard to TES-11"],
        ["TES 90%-mass", f"{tes_row.mean_selected_count:.2f}", f"{tes_row.mean_pairwise_jaccard:.3f}", f"{tes_row.nogueira_stability:.3f}", f"{tes_row.mean_jaccard_to_frozen_tes11:.3f}"],
        ["Mean-SHAP 90%-mass", f"{mean_row.mean_selected_count:.2f}", f"{mean_row.mean_pairwise_jaccard:.3f}", f"{mean_row.nogueira_stability:.3f}", f"{mean_row.mean_jaccard_to_frozen_tes11:.3f}"],
        ["Cox-score top-11 base", f"{cox_row.mean_selected_count:.2f}", f"{cox_row.mean_pairwise_jaccard:.3f}", f"{cox_row.nogueira_stability:.3f}", f"{cox_row.mean_jaccard_to_frozen_tes11:.3f}"],
    ]
    base.insert_paragraph_before(external_h, "Table 7. Resampling stability of feature-selection procedures",
                                 review=review, bold=True, size=9.5)
    base.insert_table_before(doc, external_h, stability_rows, widths=[2.20, 0.85, 1.15, 1.00, 1.30], review=review, font_size=8.1)

    cox_a = comp[(comp.method.str.startswith("Cox stability")) & (comp.cohort.eq("2013-2014 audit"))].iloc[0]
    cox_e = comp[(comp.method.str.startswith("Cox stability")) & (comp.cohort.eq("NHANES III external"))].iloc[0]
    shap_a = comp[(comp.method.str.startswith("Resampling-consensus")) & (comp.cohort.eq("2013-2014 audit"))].iloc[0]
    shap_e = comp[(comp.method.str.startswith("Resampling-consensus")) & (comp.cohort.eq("NHANES III external"))].iloc[0]
    base.insert_paragraph_before(external_h,
        f"The stability-selection comparator produced an 11-variable Cox-consensus panel but did not match TES discrimination: C=0.8549 in the audit and 0.8472 in NHANES III, versus 0.8583 and 0.8494 for TES-11 (point differences +0.0034 and +0.0022 for TES). The resampling-consensus SHAP top-11 was closer (audit C={shap_a.harrell_c:.4f}; external C={shap_e.harrell_c:.4f}) but still did not exceed TES in either cohort. These comparisons do not establish universal superiority; they show that TES is distinguishable from a generic stability wrapper and from resampling consensus under the same survival learner.",
        review=review)

    # Sensitivity summary collapsed over direction thresholds because panels are invariant.
    sens90 = sens[(sens.tes_mass_threshold.eq(0.90)) & (sens.direction_reliability_threshold.eq(0.10))].iloc[0]
    sens925 = sens[(sens.tes_mass_threshold.eq(0.925)) & (sens.direction_reliability_threshold.eq(0.10))].iloc[0]
    sens95 = sens[(sens.tes_mass_threshold.eq(0.95)) & (sens.direction_reliability_threshold.eq(0.10))].iloc[0]
    base.insert_paragraph_before(external_h,
        "The primary TES result was insensitive to the tested direction-reliability threshold: |rho| cutoffs of 0.05, 0.10, and 0.15 all returned the identical TES-11 panel at 90% score mass. The unconstrained 90% solution also contained exactly 11 variables, demonstrating that neither the minimum of 8 nor maximum of 15 determined the primary panel. Raising the score-mass requirement produced nested 13-variable (92.5%) and 15-variable (95%) panels, with only small audit/external C-index increases; thus the principal trade-off is explicit parsimony rather than threshold-induced loss of discrimination.",
        review=review)
    sens_rows = [
        ["TES mass", "Direction cutoffs", "K", "Audit C", "External C"],
        ["90%", "0.05 / 0.10 / 0.15", str(int(sens90.selected_feature_count)), f"{sens90.audit_harrell_c:.4f}", f"{sens90.external_harrell_c:.4f}"],
        ["92.5%", "0.05 / 0.10 / 0.15", str(int(sens925.selected_feature_count)), f"{sens925.audit_harrell_c:.4f}", f"{sens925.external_harrell_c:.4f}"],
        ["95%", "0.05 / 0.10 / 0.15", str(int(sens95.selected_feature_count)), f"{sens95.audit_harrell_c:.4f}", f"{sens95.external_harrell_c:.4f}"],
    ]
    base.insert_paragraph_before(external_h, "Table 8. TES threshold sensitivity in independent audit and external-era evaluation",
                                 review=review, bold=True, size=9.5)
    base.insert_table_before(doc, external_h, sens_rows, widths=[1.0, 2.15, 0.65, 1.0, 1.0], review=review, font_size=8.2)

    # Renumber later headings and table captions.
    base.set_para_text(external_h, "3.7 External-era transportability", review=review, bold=True, size=11.5)
    base.set_para_text(base.find_para(doc, "3.7 Temporal SHAP stability"), "3.8 Temporal SHAP stability", review=review, bold=True, size=11.5)
    base.set_para_text(base.find_para(doc, "3.8 Censoring-aware survival sensitivity"), "3.9 Censoring-aware survival sensitivity", review=review, bold=True, size=11.5)
    base.set_para_text(base.find_para(doc, "Table 7. Pairwise temporal stability"), "Table 9. Pairwise temporal stability of global SHAP explanations", review=review, bold=True, size=9.5)
    base.set_para_text(base.find_para(doc, "Table 8. Censoring-aware sensitivity"), "Table 10. Censoring-aware sensitivity for TES-11 AFT", review=review, bold=True, size=9.5)

    # ---------------------------- Discussion ---------------------------
    tech = base.find_para(doc, "The central technical contribution is the coupling")
    base.set_para_text(tech,
        "The central technical contribution is the coupling of a formal temporal explanation-stability selector with a frozen transportability-evaluation architecture. TES is not simply top-k SHAP: it normalizes global SHAP importance by cycle, penalizes temporal variation in magnitude, weights reliable feature-effect direction agreement, and chooses the smallest panel meeting a fixed cumulative-score criterion. The new resampling analysis adds a second axis of evidence: the resulting selector showed high perturbation stability (Nogueira 0.962; mean pairwise Jaccard 0.960), and the primary panel was invariant across a threefold range of direction-reliability thresholds. A generic Cox stability-selection consensus produced a different 11-variable panel and lower audit/external discrimination, demonstrating that TES is not reducible to subsampling recurrence alone.",
        review=review)
    comp_disc = base.find_para(doc, "The component ablation clarifies what the temporal terms add")
    base.set_para_text(comp_disc,
        "The component ablation and threshold analyses clarify what the temporal terms add without overstating predictive superiority. Importance-only selection and either one-component temporal variant retained 12 variables under the original 90% mass rule, whereas full TES retained 11. Mean-SHAP remained perfectly stable under the present resampling scheme but also retained 12 variables, and the 92.5%/95% TES mass settings produced nested 13/15-variable panels with only small discrimination gains. The evidence therefore supports a specific contribution: TES provides an explicit, stable parsimony mechanism that trades a very small amount of achievable discrimination for fewer variables while retaining audit and external-era transportability.",
        review=review)
    expl = base.find_para(doc, "The temporal SHAP results show that the model relied")
    base.set_para_text(expl,
        "The temporal SHAP rankings in NHANES were already highly stable (Spearman 0.996-0.999 with complete top-10 overlap), so this dataset does not demonstrate catastrophic explanation drift. That is informative rather than contradictory: TES is designed to make instability penalizable when present, while in this application the main empirical effect of combining magnitude stability and direction consistency was greater parsimony. The resampling results further show that the selected core is reproducible under data perturbation. Accordingly, the contribution is the explicit selection-and-audit framework, not a claim that severe explanation drift was observed in NHANES.",
        review=review)
    strengths = base.find_para(doc, "Strengths include a large population-based cohort")
    base.set_para_text(strengths,
        "Strengths include a large population-based cohort, strict chronological separation, formal TES selection, independent audit, prespecified gates, participant-paired bootstrap inference, frozen external-era evaluation, component ablation, alternative and stability-aware selection baselines, 200-resample Jaccard/Nogueira stability analysis, threshold sensitivity, censoring-aware metrics, subgroup auditing, quantitative temporal explanation stability, and an executable reviewer-ready package with source reconstruction and hash verification.",
        review=review)

    concl = base.find_para(doc, "Temporal Explanation-Stable selection provides a reproducible technical mechanism")
    base.set_para_text(concl,
        "Temporal Explanation-Stable selection provides a reproducible technical mechanism for reducing a survival-learning predictor panel while explicitly accounting for cross-cycle explanation magnitude and direction. In 52,287 contemporary NHANES participants, nonlinear survival learning improved discrimination over Cox; TES reduced 25 predictors to 11 and remained noninferior to full AFT in the independent audit and no-refit NHANES III evaluation. The joint temporal terms were required to reach the 11-variable panel under the frozen 90% mass rule, selection remained highly stable under 200 half-samples, the primary panel was invariant across direction-reliability thresholds from 0.05 to 0.15, and a Cox stability-selection consensus did not reproduce TES performance. Together with censoring-aware evaluation, chronological freezing, and executable verification, these results make TES a defensible methodological contribution for parsimonious survival machine learning under temporal shift.",
        review=review)

    # Improve pagination: remove the legacy manual page break that followed the
    # 3.2 heading in the original manuscript, then place the interpretation before
    # Table 2 and break explicitly at the table caption.
    h32 = base.find_para(doc, "3.2 Chronological model performance")
    nxt = h32._p.getnext()
    if nxt is not None and 'w:type="page"' in nxt.xml and not ''.join(nxt.itertext()).strip():
        nxt.getparent().remove(nxt)
    perf_p = base.find_para(doc, "In 2009-2012 validation")
    perf_p.paragraph_format.keep_with_next = False
    perf_p.paragraph_format.keep_together = False
    table2_cap = base.find_para(doc, "Table 2. Main chronological")
    table2_cap.paragraph_format.page_break_before = True
    table2_cap._p.addprevious(perf_p._p)

    # Metadata and global formatting after insertions.
    doc.core_properties.title = doc.paragraphs[0].text
    doc.core_properties.subject = "TES survival machine learning with resampling stability and threshold sensitivity"
    for p in doc.paragraphs:
        # Prevent accidental subtitle-style italics after deletion and keep journal-neutral black text.
        if p is doc.paragraphs[0]:
            for r in p.runs: base.set_run(r, size=16.5, bold=True)
        elif p.style.name == "Heading 1":
            for r in p.runs: base.set_run(r, size=14, bold=True)
        elif p.style.name == "Heading 2":
            for r in p.runs: base.set_run(r, size=11.5, bold=True)

    out = REVIEW_OUT if review else CLEAN_OUT
    doc.save(out)
    return out


if __name__ == "__main__":
    print(build(False))
    print(build(True))
