# Temporal Explanation-Stable (TES) selection: formal specification

This document formalizes the already frozen TES selection rule; it does not change the algorithm.

For feature j and selection cycle c, let I_jc be the normalized mean absolute SHAP importance. Let d_jc be Spearman's rho between the feature value and its SHAP contribution within cycle c.

1. Mean importance: Ibar_j = (1/C) * sum_c I_jc.
2. Temporal variation: CV_j = sd(I_j1,...,I_jC) / max(Ibar_j, epsilon).
3. Direction agreement: using cycles with |d_jc| >= 0.10, A_j = |mean(sign(d_jc))|; if none are reliable, A_j = 0.5.
4. TES score: TES_j = Ibar_j * A_j / (1 + CV_j).
5. Sort features by TES_j descending. Select the smallest K whose cumulative TES mass reaches 0.90, subject to 8 <= K <= 15, and force age and sex if absent.

The reconstructed rule selects the same 11 features as the frozen TES artifact.
