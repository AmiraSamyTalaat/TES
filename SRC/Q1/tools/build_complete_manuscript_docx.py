from pathlib import Path
import json, csv
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "publication"
OUT = PUB / "PROVLAB_COMPLETE_MANUSCRIPT_Q1_SUBMISSION_READY.docx"
BLUE = "2E74B5"; NAVY = "1F4D78"; LIGHT = "F4F6F9"; GRAY = "666666"

def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill); tcPr.append(shd)

def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc = cell._tc; tcPr = tc.get_or_add_tcPr(); tcMar = tcPr.first_child_found_in('w:tcMar')
    if tcMar is None: tcMar = OxmlElement('w:tcMar'); tcPr.append(tcMar)
    for m, v in [('top',top),('start',start),('bottom',bottom),('end',end)]:
        node = tcMar.find(qn('w:'+m))
        if node is None: node=OxmlElement('w:'+m); tcMar.append(node)
        node.set(qn('w:w'), str(v)); node.set(qn('w:type'),'dxa')

def set_repeat_table_header(row):
    trPr=row._tr.get_or_add_trPr(); e=OxmlElement('w:tblHeader'); e.set(qn('w:val'),'true'); trPr.append(e)

def set_table_widths(table, widths):
    table.autofit=False; table.alignment=WD_TABLE_ALIGNMENT.CENTER
    tblPr=table._tbl.tblPr; tblW=tblPr.first_child_found_in('w:tblW'); tblW.set(qn('w:w'),str(sum(widths))); tblW.set(qn('w:type'),'dxa')
    grid=table._tbl.tblGrid
    for child in list(grid): grid.remove(child)
    for width in widths:
        col=OxmlElement('w:gridCol'); col.set(qn('w:w'),str(width)); grid.append(col)
    for row in table.rows:
        for cell,width in zip(row.cells,widths):
            tcW=cell._tc.get_or_add_tcPr().first_child_found_in('w:tcW'); tcW.set(qn('w:w'),str(width)); tcW.set(qn('w:type'),'dxa'); set_cell_margins(cell)

def set_font(run, size=None, bold=None, italic=None, color=None):
    run.font.name='Calibri'; run._element.get_or_add_rPr().rFonts.set(qn('w:ascii'),'Calibri'); run._element.rPr.rFonts.set(qn('w:hAnsi'),'Calibri')
    if size: run.font.size=Pt(size)
    if bold is not None: run.bold=bold
    if italic is not None: run.italic=italic
    if color: run.font.color.rgb=RGBColor.from_string(color)

def add_field(paragraph, field):
    run=paragraph.add_run(); begin=OxmlElement('w:fldChar'); begin.set(qn('w:fldCharType'),'begin'); instr=OxmlElement('w:instrText'); instr.set(qn('xml:space'),'preserve'); instr.text=field; sep=OxmlElement('w:fldChar'); sep.set(qn('w:fldCharType'),'separate'); text=OxmlElement('w:t'); text.text='1'; end=OxmlElement('w:fldChar'); end.set(qn('w:fldCharType'),'end')
    for x in (begin,instr,sep,text,end): run._r.append(x)

def add_heading(doc, text, level=1):
    p=doc.add_paragraph(text, style=f'Heading {level}'); p.paragraph_format.keep_with_next=True; return p

def add_para(doc, text, bold_lead=None):
    p=doc.add_paragraph(); p.paragraph_format.widow_control=True
    if bold_lead and text.startswith(bold_lead):
        r=p.add_run(bold_lead); r.bold=True; p.add_run(text[len(bold_lead):])
    else: p.add_run(text)
    return p

def add_caption(doc, text):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next=True; p.paragraph_format.space_before=Pt(6); p.paragraph_format.space_after=Pt(4)
    r=p.add_run(text); set_font(r,9,bold=True,color=NAVY); return p

def add_table(doc, headers, rows, widths, font_size=8):
    t=doc.add_table(rows=1, cols=len(headers)); t.style='Table Grid'; set_table_widths(t,widths)
    for i,h in enumerate(headers):
        c=t.rows[0].cells[i]; c.text=str(h); set_cell_shading(c,LIGHT); c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for r in c.paragraphs[0].runs: set_font(r,font_size,bold=True,color=NAVY)
    set_repeat_table_header(t.rows[0])
    for vals in rows:
        cells=t.add_row().cells
        for i,v in enumerate(vals):
            cells[i].text=str(v); cells[i].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cells[i].paragraphs:
                p.paragraph_format.space_after=Pt(0)
                for r in p.runs: set_font(r,font_size)
    set_table_widths(t,widths); doc.add_paragraph().paragraph_format.space_after=Pt(2); return t

def load_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))

doc=Document(); sec=doc.sections[0]
sec.page_width=Inches(8.5); sec.page_height=Inches(11); sec.top_margin=Inches(0.85); sec.bottom_margin=Inches(0.8); sec.left_margin=Inches(0.9); sec.right_margin=Inches(0.9)
styles=doc.styles
normal=styles['Normal']; normal.font.name='Calibri'; normal._element.rPr.rFonts.set(qn('w:ascii'),'Calibri'); normal._element.rPr.rFonts.set(qn('w:hAnsi'),'Calibri'); normal.font.size=Pt(11); normal.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; normal.paragraph_format.space_after=Pt(8); normal.paragraph_format.line_spacing=1.25
for name,size,color,before,after in [('Heading 1',16,BLUE,16,8),('Heading 2',13,BLUE,12,6),('Heading 3',12,NAVY,8,4)]:
    s=styles[name]; s.font.name='Calibri'; s._element.rPr.rFonts.set(qn('w:ascii'),'Calibri'); s._element.rPr.rFonts.set(qn('w:hAnsi'),'Calibri'); s.font.size=Pt(size); s.font.bold=True; s.font.color.rgb=RGBColor.from_string(color); s.paragraph_format.space_before=Pt(before); s.paragraph_format.space_after=Pt(after)
header=sec.header.paragraphs[0]; header.alignment=WD_ALIGN_PARAGRAPH.RIGHT; hr=header.add_run('PROVLAB | Working manuscript'); set_font(hr,8,color=GRAY)
footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER; fr=footer.add_run('Page '); set_font(fr,8,color=GRAY); add_field(footer,'PAGE')

# Cover
p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(70); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=p.add_run('ORIGINAL RESEARCH'); set_font(r,11,bold=True,color=BLUE)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(14)
r=p.add_run('Chronologically Frozen and Externally Validated Survival Machine Learning with a Parsimonious Explanation-Stable Laboratory Panel'); set_font(r,22,bold=True,color=NAVY)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run('A survey-aware NHANES study with a parsimonious 11-variable model'); set_font(r,14,italic=True,color=GRAY)
doc.add_paragraph(); p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run('[Author names and affiliations to be inserted]'); set_font(r,11,bold=True)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run('Corresponding author: [name, institution, email]'); set_font(r,10,color=GRAY)
doc.add_paragraph(); p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; r=p.add_run('Complete scientific working draft | 28 August 2026'); set_font(r,10,color=GRAY)
doc.add_page_break()

add_heading(doc,'Abstract',1)
for h,text in [
('Background','Survival models developed using random data splits may overstate generalizability when clinical measurements, population composition, and follow-up change across calendar time. We evaluated chronological and external-era transportability of explainable survival learning using routinely measured laboratory variables and tested whether a substantially smaller panel could retain discrimination.'),
('Methods','Adults from NHANES 1999-2018 were linked to public-use mortality outcomes. Models were developed on 1999-2008, validated on 2009-2012, audited on 2013-2014, and evaluated under frozen temporal protocols in 2015-2018. Cox proportional hazards, XGBoost-Cox, and XGBoost accelerated failure time (AFT) models were compared using participant-paired bootstrap confidence intervals for Harrell\'s C-index. Temporal Explanation-Stable selection produced an 11-variable AFT panel (TES-11). Models were tested without refitting in an independently harmonized NHANES III external-era cohort. Temporal SHAP analyses quantified explanation stability.'),
('Results','The contemporary cohort included 52,287 adults and 8,311 deaths. In 2009-2012 validation, XGBoost-Cox outperformed Cox (C-index 0.8608 vs 0.8486; difference 0.0122, 95% CI 0.0093-0.0149). XGBoost-AFT provided a smaller additional gain (0.00135, 95% CI 0.00020-0.00250). The external NHANES III cohort included 16,519 adults and 7,081 deaths. External C-indices were 0.8512 for XGBoost-Cox, 0.8508 for full AFT, and 0.8494 for TES-11. TES-11 reduced the predictor panel by 56% and remained noninferior to full AFT externally (difference -0.00144, 95% CI -0.00221 to -0.00068; margin -0.005).'),
('Conclusions','Nonlinear survival learning using routine laboratory measurements maintained strong discrimination across chronological and substantially earlier external survey eras. An 11-variable panel preserved nearly all full-panel discrimination. Frozen chronological evaluation, external-era testing, and temporal explanation auditing provide a rigorous framework for assessing transportability.')]:
    p=doc.add_paragraph(); rr=p.add_run(h+': '); rr.bold=True; p.add_run(text)
p=doc.add_paragraph(); rr=p.add_run('Keywords: '); rr.bold=True; p.add_run('survival analysis; NHANES; XGBoost; accelerated failure time; temporal validation; external validation; SHAP; transportability')

add_heading(doc,'1. Introduction',1)
add_para(doc,'Clinical risk-prediction models are commonly evaluated using random train-test splits. Although convenient, random splits mix calendar eras and may conceal deterioration caused by changes in laboratory practice, population composition, follow-up, and predictor-outcome relationships. For time-to-event outcomes, evaluation is further complicated by right censoring and by the need for reliable discrimination and calibration [3,4,10-12].')
add_para(doc,'Machine-learning survival models can represent nonlinear effects and interactions beyond a conventional proportional-hazards specification [3-5]. Contemporary reporting and risk-of-bias guidance emphasizes transparent validation, prespecified analysis, and evaluation beyond apparent model fit [8,9]. A strong transportability assessment should preserve chronology, freeze analytic choices before confirmatory testing, quantify uncertainty in paired model differences, examine population subgroups, and test the model in a distinct external era without refitting.')
add_para(doc,'Explainability introduces an additional transportability question. SHAP provides local and global decompositions of tree-model predictions [6,7], but a single explanation plot cannot establish whether feature rankings, magnitudes, and directions remain stable as populations change. Likewise, a large laboratory panel may provide only marginal gains over a smaller, operationally practical set of routinely measured variables.')
add_heading(doc,'1.1 Related work and research gap',2)
add_para(doc,'Survival prediction has progressed from semiparametric Cox models to nonlinear boosted-tree objectives that accommodate complex predictor-response structures [3-5]. Explainable artificial intelligence has improved inspection of tree ensembles [6,7], while TRIPOD+AI and PROBAST+AI have raised expectations for transparent reporting, representative validation, and bias assessment [8,9]. Yet these components are often evaluated separately: random or single-era validation can obscure temporal drift; feature reduction can ignore stability across cycles; and one-time explanation summaries can mask changes in model reliance.')
add_para(doc,'The unresolved methodological gap is therefore an integrated evaluation that jointly tests chronological transportability, external-era generalization without refitting, parsimonious noninferiority, and temporal explanation stability under a frozen protocol. NHANES and its public-use mortality linkage provide a population-based setting in which these questions can be examined across multiple survey eras [1,2].')
add_heading(doc,'1.2 Study objective and main contributions',2)
add_para(doc,'We evaluated whether nonlinear survival learning trained on NHANES 1999-2008 maintained discrimination across later cycles and NHANES III, whether an accelerated failure-time objective improved performance, and whether a temporally stable 11-variable panel retained full-panel discrimination. The study makes five technical contributions:')
for lead, body in [
('Chronologically frozen evaluation. ', 'A six-stage design separates development, validation, audit, confirmation, stress testing, and external-era evaluation, with analytic choices locked before outcomes were opened.'),
('Censoring-aware comparative inference. ', 'Cox, XGBoost-Cox, and XGBoost-AFT are compared using participant-paired bootstrap confidence intervals rather than unpaired point estimates.'),
('Prespecified parsimonious noninferiority. ', 'TES-11 reduces the laboratory panel by 56% and is tested against the full AFT model using a fixed C-index margin internally and externally.'),
('Temporal explanation auditing. ', 'Global SHAP rankings, magnitudes, top-feature overlap, and direction reversals are quantified across survey cycles instead of relying on a single explanation plot.'),
('Transportability and reproducibility controls. ', 'The framework combines subgroup and survey-weight sensitivity analyses, no-refit NHANES III evaluation, executable code, protocol freezes, and model/configuration hashes.')]:
    p=doc.add_paragraph(style='List Bullet'); rr=p.add_run(lead); rr.bold=True; p.add_run(body)

add_heading(doc,'2. Methods',1)
add_heading(doc,'2.1 Data sources and study population',2)
add_para(doc,'The primary data source was the US National Health and Nutrition Examination Survey (NHANES), a continuing cross-sectional survey using a complex, multistage probability design. Public-use linked mortality files supplied vital-status and follow-up information. Adults aged 20 years or older with eligible mortality linkage were included. The contemporary cohort comprised ten two-year cycles from 1999-2000 through 2017-2018. NHANES III served as an external-era cohort after independent variable harmonization.')
add_para(doc,'Predictors comprised age, sex, and routinely measured serum biochemistry analytes available across the selected cycles. Laboratory variables were harmonized to common SI units. Missing numerical values were passed to tree models using their native missing-value handling; the Cox baseline used the prespecified preprocessing implemented in the frozen analysis pipeline. The outcome was all-cause mortality, with time measured in months from examination to death or censoring.')
add_heading(doc,'2.2 Chronological design and freezing',2)
add_para(doc,'The analysis followed calendar chronology: 1999-2008 for model development, 2009-2012 for validation, 2013-2014 for development audit, 2015-2016 for frozen temporal confirmation, and 2017-2018 as a short-follow-up stress test. The substantially earlier NHANES III cohort was opened for external evaluation only after model, configuration, and execution hashes had been frozen. No model refitting was performed on NHANES III outcomes.')
add_caption(doc,'Figure 1. Study timeline and locked evaluation stages')
doc.add_picture(str(PUB/'figures'/'FIGURE1_STUDY_TIMELINE.png'),width=Inches(6.55)); doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
add_heading(doc,'2.3 Models',2)
add_para(doc,'The prespecified comparators were a full-panel Cox proportional-hazards model, gradient-boosted trees with a Cox objective (XGBoost-Cox), and gradient-boosted trees with an accelerated failure-time objective (XGBoost-AFT). The AFT learner represented uncensored deaths as exact time intervals and right-censored observations as intervals extending from the last observed time to infinity. Hyperparameters, maximum boosting rounds, early stopping, and progression thresholds were recorded before confirmatory use.')
add_para(doc,'TES-11 was derived using Temporal Explanation-Stable selection. For each feature, normalized mean absolute SHAP importance was combined with its temporal coefficient of variation and agreement in feature-effect direction across development-era cycles. The smallest panel reaching 90% of stable-score mass was retained subject to a minimum of 8 and maximum of 15 variables, with age and sex forced. This procedure selected 11 variables: age, sex, ALT, GGT, glucose, alkaline phosphatase, chloride, albumin, blood urea nitrogen, potassium, and lactate dehydrogenase.')
add_heading(doc,'2.4 Evaluation and statistical analysis',2)
add_para(doc,'Harrell\'s concordance index was the principal discrimination metric. Differences between models were estimated using participant-paired bootstrap resampling so that both models were evaluated on identical replicate samples. A 95% percentile bootstrap confidence interval excluding zero supported a directional performance difference. TES-11 noninferiority was assessed against full AFT using a prespecified C-index margin of -0.005.')
add_para(doc,'Subgroup audits were conducted for female and male participants and for ages 20-39, 40-59, and 60 years or older. Complex-survey examination weights were evaluated in sensitivity analyses. Because administrative follow-up was especially short in 2017-2018, that cycle was treated as a discrimination stress test rather than evidence for fixed five-year risk performance.')
add_heading(doc,'2.5 Temporal explainability analysis',2)
add_para(doc,'TreeSHAP was calculated independently in the 2009-2010, 2011-2012, and 2013-2014 cycles [6,7]. Stability was quantified using Spearman correlation of global importance, Jensen-Shannon divergence of normalized importance magnitudes, top-10 overlap, and the fraction of reliable feature directions that reversed sign.')
add_heading(doc,'2.6 Reproducibility and claim control',2)
add_para(doc,'The analysis retained protocol-freeze files, model and configuration hashes, machine-readable status reports, and explicit progression gates. Public-use data and a script-based workflow support computational reproducibility subject to source-data access terms.')

add_heading(doc,'3. Results',1)
add_heading(doc,'3.1 Cohort characteristics',2)
coh=load_csv(PUB/'TABLE1_COHORT_CHARACTERISTICS.csv')
rows=[]
for x in coh:
    rows.append([x['cohort'],f"{int(x['participants_n']):,}",f"{int(x['deaths_n']):,}",f"{100*float(x['unweighted_death_fraction']):.1f}%",f"{float(x['median_followup_months']):.0f}",f"{float(x['survey_weighted_mean_age_years']):.1f}",f"{100*float(x['survey_weighted_female_fraction']):.1f}%"])
add_caption(doc,'Table 1. Cohort characteristics by chronological evaluation stage')
add_table(doc,['Cohort','N','Deaths','Deaths %','Median follow-up, mo','Weighted age, y','Weighted female'],rows,[3180,880,880,900,1350,1100,1070],7.2)
add_para(doc,'The contemporary cohort included 52,287 participants and 8,311 deaths. Event fractions and median follow-up declined in later cycles because mortality linkage ended at a common administrative date. NHANES III contributed 16,519 external-era participants, 7,081 deaths, and a median follow-up of 316 months.')
add_heading(doc,'3.2 Chronological model performance',2)
res=load_csv(PUB/'FINAL_RESULTS_TABLE.csv'); rows=[]
for x in res:
    ci='' if not x['ci95_lower'] else f"{float(x['ci95_lower']):.4f} to {float(x['ci95_upper']):.4f}"
    gain='' if not x['gain'] else f"{float(x['gain']):+.4f}"
    rows.append([x['analysis'],x['model'],f"{float(x['c_index']):.4f}",gain,ci,x['status']])
doc.add_page_break()
add_caption(doc,'Table 2. Main chronological and external-era discrimination results')
add_table(doc,['Analysis','Model','C-index','Difference','95% CI','Decision'],rows,[2350,1830,800,850,1760,1650],7.5)
add_para(doc,'In 2009-2012 validation, full Cox achieved C=0.8486. XGBoost-Cox improved discrimination to 0.8608, with a paired gain of 0.0122 (95% CI 0.0093-0.0149). XGBoost-AFT reached 0.8621 and provided a smaller but statistically supported gain over XGBoost-Cox. The nonlinear advantage over Cox persisted in frozen 2015-2016 confirmation and in the 2017-2018 short-follow-up stress test.')
add_caption(doc,'Figure 2. Paired C-index differences across chronological and external evaluations')
doc.add_picture(str(PUB/'figures'/'FIGURE2_CINDEX_FOREST.png'),width=Inches(6.55)); doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER
add_heading(doc,'3.3 Subgroup performance',2)
sub=json.loads((ROOT/'outputs'/'subgroup_audit'/'SUBGROUP_AUDIT_STATUS.json').read_text())['groups']; rows=[]
for x in sub: rows.append([x['group'].replace('_',' '),f"{x['rows']:,}",f"{x['events']:,}",f"{x['cox_c']:.3f}",f"{x['xgboost_c']:.3f}",f"{x['paired_gain']:+.3f}",f"{x['gain_ci95_lower']:.3f} to {x['gain_ci95_upper']:.3f}"])
add_caption(doc,'Table 3. Prespecified validation subgroup audit')
add_table(doc,['Subgroup','N','Deaths','Cox C','XGB-Cox C','Gain','95% CI'],rows,[1500,850,850,900,1100,850,2510],7.5)
add_para(doc,'XGBoost-Cox improved discrimination in both sexes and all age groups. Absolute C-index was lower among participants aged 20-39 years, where only 60 deaths occurred and the confidence interval was correspondingly wide. The subgroup results support consistency of the nonlinear gain but do not establish equal calibration or clinical utility across subgroups.')
add_heading(doc,'3.4 Parsimonious TES-11 panel',2)
add_para(doc,'TES-11 reduced the full 25-variable predictor panel to 11 variables, a 56% reduction. In the 2013-2014 audit, TES-11 achieved C=0.8583 compared with 0.8591 for full AFT (difference -0.00077, 95% CI -0.00286 to 0.00129). In NHANES III, TES-11 achieved C=0.8494 compared with 0.8508 for full AFT (difference -0.00144, 95% CI -0.00221 to -0.00068). Both differences were within the prespecified noninferiority margin of -0.005.')
features=['Age','Sex','Alanine aminotransferase (ALT)','Gamma-glutamyl transferase (GGT)','Glucose','Alkaline phosphatase','Chloride','Albumin','Blood urea nitrogen','Potassium','Lactate dehydrogenase (LDH)']
add_caption(doc,'Table 4. TES-11 predictor panel')
feature_rows=[]
for i in range(6):
    left=[i+1,features[i]]
    j=i+6
    right=[j+1,features[j]] if j < len(features) else ['', '']
    feature_rows.append(left+right)
add_table(doc,['No.','Predictor','No.','Predictor'],feature_rows,[650,4030,650,4030],8.5)
add_heading(doc,'3.5 External-era transportability',2)
add_para(doc,'In the NHANES III external-era cohort, XGBoost-Cox, full AFT, and TES-11 all maintained C-indices close to 0.85 without refitting. Full AFT was externally equivalent rather than superior to XGBoost-Cox: the difference was -0.00036 (95% CI -0.00095 to 0.00024). These findings support transport of rank discrimination across a large calendar-era shift while cautioning against claiming external superiority of the AFT objective.')
add_heading(doc,'3.6 Temporal SHAP stability',2)
sh=json.loads((ROOT/'outputs'/'temporal_shap_stability'/'TEMPORAL_SHAP_STABILITY_STATUS.json').read_text())['pairwise']; rows=[]
for x in sh: rows.append([f"{x['cycle_a']} vs {x['cycle_b']}",f"{x['importance_spearman']:.3f}",f"{x['importance_js_divergence']:.5f}",f"{x['top10_overlap']:.2f}",f"{x['direction_flip_fraction']:.2f}"])
add_caption(doc,'Table 5. Pairwise temporal stability of global SHAP explanations')
add_table(doc,['Cycle comparison','Spearman rho','JS divergence','Top-10 overlap','Direction flip fraction'],rows,[2700,1450,1600,1600,2010],8)
add_para(doc,'Global importance rankings were highly stable (Spearman rho 0.996-0.999), top-10 overlap was complete, and normalized magnitude divergence was small. Reliable feature-effect directions showed no reversals in two comparisons and a 5% reversal fraction in the longest comparison. Age dominated global importance, followed by sex and routine liver, glycemic, renal, electrolyte, and protein markers.')
add_caption(doc,'Figure 3. Temporal stability of normalized global SHAP importance. A logarithmic color scale reveals between-feature differences while cell labels report the original normalized values.')
doc.add_picture(str(PUB/'figures'/'FIGURE3_TEMPORAL_SHAP_HEATMAP.png'),width=Inches(5.10)); doc.paragraphs[-1].alignment=WD_ALIGN_PARAGRAPH.CENTER

add_heading(doc,'4. Discussion',1)
add_para(doc,'This study provides evidence that nonlinear survival learning based on routine laboratory measurements can maintain strong discrimination across both later NHANES cycles and a substantially earlier external survey era. Three findings are central. First, XGBoost-Cox consistently improved rank discrimination over a full-panel Cox baseline. Second, the AFT objective produced a small validation improvement but was externally equivalent to XGBoost-Cox. Third, an 11-variable temporally stable panel retained nearly all full-panel performance internally and externally.')
add_heading(doc,'4.1 Technical contribution and interpretation',2)
add_para(doc,'The central technical contribution is an integrated transportability-evaluation framework for survival machine learning. Chronological separation, pre-confirmatory freezing, paired uncertainty, external-era evaluation without refitting, survey-design sensitivity, prespecified parsimony, and temporal explanation auditing are combined in one reproducible workflow. This integration converts transportability from a single performance number into a multidimensional test of discrimination, stability, subgroup consistency, and reproducibility.')
add_para(doc,'The AFT objective added a complementary censoring-aware representation of survival time and achieved a statistically supported validation gain. External equivalence between AFT and Cox-objective boosting then provided a principled selection signal: parsimony and stability, rather than a negligible external C-index difference, become decisive model attributes.')
add_heading(doc,'4.2 Clinical and operational relevance',2)
add_para(doc,'TES-11 is operationally attractive because it uses age, sex, and nine routinely available analytes while preserving C-index within 0.002 of full AFT externally. The 56% panel reduction lowers measurement burden and yields a compact risk-ranking tool suitable for prospective calibration, decision-curve analysis, and implementation studies.')
add_heading(doc,'4.3 Explainability and transportability',2)
add_para(doc,'The temporal SHAP results show that the model relied on a stable predictor hierarchy across adjacent cycles. Near-perfect rank correlations, complete top-10 overlap, small magnitude divergence, and few direction reversals provide convergent evidence that performance was not driven by a transient feature ordering. This quantitative temporal audit extends explainability from a descriptive snapshot to a reproducible transportability criterion.')
add_heading(doc,'4.4 Strengths',2)
p=doc.add_paragraph(style='List Bullet'); p.add_run('Strengths include a large population-based cohort, strict chronological separation, prespecified gates, paired bootstrap inference, frozen external-era evaluation, parsimony analysis, subgroup auditing, and quantitative temporal explanation stability.')
add_heading(doc,'4.5 Scope and limitations',2)
p=doc.add_paragraph(style='List Bullet'); p.add_run('Public-use mortality files may include perturbation and restricted cause-specific detail; the endpoint was therefore all-cause mortality.')
p=doc.add_paragraph(style='List Bullet'); p.add_run('NHANES is observational and US-based; transport to health systems, countries, or contemporary clinical workflows was not established.')
p=doc.add_paragraph(style='List Bullet'); p.add_run('Later cycles had shorter administrative follow-up. The 2017-2018 analysis was restricted to discrimination stress testing and cannot support five-year risk claims.')
p=doc.add_paragraph(style='List Bullet'); p.add_run('Discrimination near 0.85 does not itself establish calibration, net benefit, fairness, or prospective clinical utility.')
p=doc.add_paragraph(style='List Bullet'); p.add_run('SHAP values explain the fitted model and may reflect confounding and predictor correlation; they are not causal effect estimates.')
add_heading(doc,'4.6 Future directions',2)
add_para(doc,'The next validation phase should estimate horizon-specific calibration in cohorts with sufficiently long follow-up, quantify net benefit using decision-curve analysis, and test prospective recalibration across health systems and countries. These extensions will determine whether the compact TES-11 panel can progress from robust population risk ranking to decision-support evaluation.')

add_heading(doc,'5. Conclusions',1)
add_para(doc,'Explainable nonlinear survival models trained on routine NHANES laboratory data maintained strong discrimination across chronological tests and a substantially earlier external era. XGBoost-based survival learning improved discrimination over Cox, while TES-11 achieved a 56% reduction in predictors with prespecified internal and external noninferiority. The integrated framework contributes four mutually reinforcing safeguards—chronological freezing, paired inference, no-refit external-era testing, and quantitative temporal explanation auditing—and provides a reproducible foundation for prospective calibration and decision-support evaluation.')

add_heading(doc,'Declarations',1)
for h,t in [('Author contributions','A.S.T. conceived and conducted the study, performed the analyses, interpreted the results, prepared the manuscript, and approved the final version.'),('Funding','Not applicable.'),('Data availability','NHANES examination data and public-use linked mortality files are publicly available from the US Centers for Disease Control and Prevention/National Center for Health Statistics [1,2]. The executable analysis code, protocol freezes, configuration files, and result-verification artifacts are contained in the reviewer-ready project package.'),('Ethics approval and consent to participate','Not applicable to this secondary analysis of publicly available, de-identified data. NHANES protocols and original participant consent were administered by the National Center for Health Statistics.'),('Informed consent','Not applicable to this secondary analysis; original NHANES participants provided consent under National Center for Health Statistics protocols.'),('Consent for publication','Not applicable.'),('Competing interests','The author declares no competing interests.')]:
    add_heading(doc,h,2); add_para(doc,t)

add_heading(doc,'References',1)
refs=[
'National Center for Health Statistics. National Health and Nutrition Examination Survey: survey methods and analytic guidelines. Centers for Disease Control and Prevention. https://www.cdc.gov/nchs/nhanes/ (accessed 29 August 2026).',
'National Center for Health Statistics. Public-use linked mortality files. Centers for Disease Control and Prevention. https://www.cdc.gov/nchs/linked-data/mortality-files/index.html (accessed 29 August 2026).',
'Cox DR. Regression models and life-tables. J R Stat Soc Series B Stat Methodol. 1972;34:187-220. doi:10.1111/j.2517-6161.1972.tb00899.x.',
'Harrell FE Jr. Regression Modeling Strategies. 2nd ed. Springer; 2015. doi:10.1007/978-3-319-19425-7.',
'Chen T, Guestrin C. XGBoost: A scalable tree boosting system. Proceedings of KDD. 2016:785-794. doi:10.1145/2939672.2939785.',
'Lundberg SM, Lee SI. A unified approach to interpreting model predictions. Advances in Neural Information Processing Systems. 2017;30.',
'Lundberg SM, Erion G, Chen H, et al. From local explanations to global understanding with explainable AI for trees. Nat Mach Intell. 2020;2:56-67. doi:10.1038/s42256-019-0138-9.',
'Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ. 2024;385:e078378. doi:10.1136/bmj-2023-078378.',
'Moons KGM, Damen JAA, Kaul T, et al. PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods. BMJ. 2025;388:e082505. doi:10.1136/bmj-2024-082505.',
'Steyerberg EW. Clinical Prediction Models. 2nd ed. Springer; 2019. doi:10.1007/978-3-030-16399-0.',
'Uno H, Cai T, Pencina MJ, D’Agostino RB Sr, Wei LJ. On the C-statistics for evaluating overall adequacy of risk prediction procedures with censored survival data. Stat Med. 2011;30:1105-1117. doi:10.1002/sim.4154.',
'Van Calster B, McLernon DJ, van Smeden M, Wynants L, Steyerberg EW. Calibration: the Achilles heel of predictive analytics. BMC Med. 2019;17:230. doi:10.1186/s12916-019-1466-7.'
]
for i,ref in enumerate(refs,1):
    p=doc.add_paragraph(style='List Number'); p.add_run(ref)

# keep captions with following images and set core properties
doc.core_properties.title='Chronologically Frozen and Externally Validated Survival Machine Learning with a Parsimonious Explanation-Stable Laboratory Panel'
doc.core_properties.subject='Complete scientific working manuscript'
doc.core_properties.author='[Authors to be inserted]'
doc.core_properties.keywords='NHANES; survival analysis; XGBoost; AFT; SHAP; temporal validation'
doc.save(OUT)
print(OUT)
