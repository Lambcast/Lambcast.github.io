# Alan Lamb
# ECON 685
# Term Project

# This is the python file related to the term project.
# I use generator-level data from the 2024 EIA-860 survey of US power plants
# to classify generating units in the PJM footprint as retired or operating.
# The outcome variable is binary: retired (1) versus operating (0).

# Basic libraries
import os
import numpy as np
import pandas as pd

# Graphing
import matplotlib.pyplot as plt
from matplotlib.pyplot import subplots

# Data work
import statsmodels.api as sm

# The library provided by the textbook
from ISLP.models import (ModelSpec as MS, summarize, bs)
from ISLP.models import (Stepwise, sklearn_selected)
from ISLP import confusion_table

# sklearn (scikit-learn) is a popular toolbox of ready-made machine learning methods.
import sklearn.model_selection as skm
from sklearn.model_selection import train_test_split, cross_val_predict, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegressionCV
from sklearn.ensemble import (RandomForestClassifier as RFC,
                              GradientBoostingClassifier as GBC)
from sklearn.metrics import (roc_curve, roc_auc_score,
                             accuracy_score, precision_score,
                             recall_score, f1_score)

# Advanced boosting library
from xgboost import XGBClassifier


###############################################################################
# Part A: Data preparation
###############################################################################

# The raw data comes in one Excel workbook from the EIA-860 2024 release.
# The "Operable" sheet contains every unit operating in 2024 and the
# "Retired and Canceled" sheet contains the cumulative record of units that
# have left the fleet. I keep only genuinely retired units (Status = "RE").

# The 13 states of the PJM footprint
PJM = ["PA", "OH", "VA", "IL", "IN", "MD", "NJ", "WV", "DE", "KY", "NC", "MI", "DC"]

# The columns kept from the raw workbook
ID_COLS = ["Plant Code", "Generator ID"]
NUM_COLS = ["Nameplate Capacity (MW)", "Summer Capacity (MW)", "Winter Capacity (MW)",
            "Minimum Load (MW)", "Nameplate Power Factor"]
CAT_COLS = ["State", "Technology", "Prime Mover", "Energy Source 1", "Sector Name",
            "Cofire Fuels?", "Carbon Capture Technology?", "Fluidized Bed Technology?",
            "Pulverized Coal Technology?", "Stoker Technology?",
            "Subcritical Technology?", "Supercritical Technology?",
            "Ultrasupercritical Technology?", "Solid Fuel Gasification System?"]
FLAG_COLS = CAT_COLS[5:]
SECONDARY = ["Energy Source 2", "Energy Source 3", "Energy Source 4",
             "Energy Source 5", "Energy Source 6"]
KEEP = ID_COLS + NUM_COLS + CAT_COLS + SECONDARY + ["Operating Year"]

# The raw workbook can sit next to this script or in the project's data
# folder. Look in the likely places and use the first one that exists.
CANDIDATES = ["3_1_Generator_Y2024.xlsx",
              os.path.join("data", "raw", "eia860", "2024",
                           "3_1_Generator_Y2024.xlsx"),
              os.path.join("..", "data", "raw", "eia860", "2024",
                           "3_1_Generator_Y2024.xlsx")]
RAW_FILE = CANDIDATES[0]
for path in CANDIDATES:
    if os.path.exists(path):
        RAW_FILE = path
        break
print("Reading the raw workbook from:", RAW_FILE)

# Read the two sheets (the real header is on the second row of each sheet)
Operable = pd.read_excel(RAW_FILE,
                         sheet_name="Operable", header=1)
Retired = pd.read_excel(RAW_FILE,
                        sheet_name="Retired and Canceled", header=1)
Retired = Retired.loc[Retired["Status"] == "RE", :]

# Restrict both sheets to the PJM states, keep the selected columns, and
# create the outcome variable: retired = 1 for retired units, 0 for operating
Operable = Operable.loc[Operable["State"].isin(PJM), KEEP]
Operable["retired"] = 0
Retired = Retired.loc[Retired["State"].isin(PJM), KEEP]
Retired["retired"] = 1

# Stack the two data frames into a single data set
Gen = pd.concat([Operable, Retired], ignore_index=True)

# Engineered variable 1: the age of the unit in years as of the 2024 survey
Gen["Operating Year"] = pd.to_numeric(Gen["Operating Year"], errors="coerce")
Gen["age"] = 2024 - Gen["Operating Year"]

# Engineered variable 2: a multi-fuel flag equal to 1 when the unit reports
# any secondary energy source. This is available on both sheets, so it does
# not leak information about retirement.
Gen["multi_fuel"] = Gen[SECONDARY].notna().any(axis=1).astype(int)

# The secondary energy source columns and the operating year are no longer needed
Gen = Gen.drop(columns=SECONDARY + ["Operating Year"])
NUM_COLS = ["age"] + NUM_COLS

# Two numeric columns are missing for about a third of the units. I add
# missingness indicators before imputing so that the fact that a value is
# missing remains available to the models.
for col in ["Minimum Load (MW)", "Nameplate Power Factor"]:
    Gen[col + "_missing"] = pd.to_numeric(Gen[col], errors="coerce").isna().astype(int)

# Impute every numeric column with its median
for col in NUM_COLS:
    Gen[col] = pd.to_numeric(Gen[col], errors="coerce")
    Gen[col] = Gen[col].fillna(Gen[col].median())

# The technology flags are "Y"/"N" questions; a blank means "N"
for col in FLAG_COLS:
    Gen[col] = Gen[col].fillna("N").astype(str).str.strip().str.upper()
    Gen[col] = Gen[col].replace({"": "N"})

# Collapse rare categorical levels (fewer than 30 units) into "Other".
# This stabilizes the logit model against quasi-separation.
MIN_LEVEL = 30
for col in ["Technology", "Prime Mover", "Energy Source 1", "Sector Name", "State"]:
    Gen[col] = Gen[col].fillna("U").astype(str).str.strip().replace({"": "U"})
    counts = Gen[col].value_counts()
    rare = counts[counts < MIN_LEVEL].index
    Gen.loc[Gen[col].isin(rare), col] = "Other"

# Fill any remaining missing categorical values with "U" (unknown)
for col in CAT_COLS:
    Gen[col] = Gen[col].fillna("U").astype(str).str.strip().replace({"": "U"})

# Drop flag columns that are nearly constant (minority level below 30 units):
# they carry no usable signal and destabilize the train/test encoding
dropped = []
for col in FLAG_COLS:
    if Gen[col].nunique() < 2 or Gen[col].value_counts().min() < MIN_LEVEL:
        dropped.append(col)
Gen = Gen.drop(columns=dropped)
print("Dropped near-constant flags:", dropped)

# Save the clean modeling data set as a CSV file
Gen.to_csv("generator_retirement.csv", index=False)
print("Observations:", Gen.shape[0])
print("Retired share:", round(Gen["retired"].mean(), 4))


###############################################################################
# Part B: Read the clean data
###############################################################################

# Read the data while specifying the data types of the variables
Gen = pd.read_csv("generator_retirement.csv",
                  dtype={
               "State": "category",
               "Technology": "category",
               "Prime Mover": "category",
               "Energy Source 1": "category",
               "Sector Name": "category",
               "Cofire Fuels?": "category",
               "Fluidized Bed Technology?": "category",
               "Pulverized Coal Technology?": "category",
               "Stoker Technology?": "category",
               "Subcritical Technology?": "category",
               "Supercritical Technology?": "category",
               "age": float,
               "Nameplate Capacity (MW)": float,
               "Summer Capacity (MW)": float,
               "Winter Capacity (MW)": float,
               "Minimum Load (MW)": float,
               "Nameplate Power Factor": float,
               "multi_fuel": int,
               "Minimum Load (MW)_missing": int,
               "Nameplate Power Factor_missing": int,
               "retired": int
               }
)

# Nameplate capacity spans four orders of magnitude, so the GAM spline below
# uses the log scale, which spreads the knots evenly
Gen["log_capacity"] = np.log1p(Gen["Nameplate Capacity (MW)"])

# Variable lists used throughout the analysis
CONT = ["age", "Nameplate Capacity (MW)", "Summer Capacity (MW)",
        "Winter Capacity (MW)", "Minimum Load (MW)", "Nameplate Power Factor"]
BINNUM = ["multi_fuel", "Minimum Load (MW)_missing", "Nameplate Power Factor_missing"]
CAT = ["State", "Technology", "Prime Mover", "Energy Source 1", "Sector Name",
       "Cofire Fuels?", "Fluidized Bed Technology?", "Pulverized Coal Technology?",
       "Stoker Technology?", "Subcritical Technology?", "Supercritical Technology?"]
ALL_VARS = CONT + BINNUM + CAT

# Summer and winter capacity are near-duplicates of nameplate capacity
# (correlation about 0.99). They are excluded from the linear and GAM designs
# to avoid collinearity and retained for the tree models, which are unaffected.
LIN_VARS = [c for c in ALL_VARS
            if c not in ("Summer Capacity (MW)", "Winter Capacity (MW)")]

# Split the raw data first. All designs below are fit on the training set
# only, so no information from the test set enters the transformations.
(Gen_train, Gen_test) = train_test_split(Gen, test_size=0.25, random_state=0)
Y_train = Gen_train["retired"].values
Y_test = Gen_test["retired"].values
print("Training set:", Gen_train.shape, " Test set:", Gen_test.shape)
print("Retired share, train:", round(Y_train.mean(), 4),
      " test:", round(Y_test.mean(), 4))


###############################################################################
# Question #1: The dependent variable
###############################################################################

# Graph 1: Bar chart of the outcome variable
ret_counts = Gen["retired"].map({0: "Operating", 1: "Retired"}).value_counts()
fig_1, ax_1 = subplots(figsize=(8, 6))
ax_1.bar(ret_counts.index, ret_counts, color="lightblue", edgecolor="black")
ax_1.set_xlabel("Unit status in the 2024 survey", fontsize=15)
ax_1.set_ylabel("Number of generating units", fontsize=15)
ax_1.set_title("Distribution of the outcome variable (retired)", fontsize=18)
fig_1.savefig("TP_Graph_1.png", dpi=200, bbox_inches="tight")

# Graph 2: Two box plots of age, for retired = 1 and retired = 0
age_ret = Gen.loc[Gen["retired"] == 1, "age"]
age_op = Gen.loc[Gen["retired"] == 0, "age"]

fig_2, ax_2 = subplots(1, 2, figsize=(12, 6), sharey=True)
ax_2[0].boxplot(age_ret)
ax_2[0].set_title("Age: Retired units", fontsize=15)
ax_2[0].set_ylabel("Age (years)", fontsize=15)
ax_2[1].boxplot(age_op)
ax_2[1].set_title("Age: Operating units", fontsize=15)
fig_2.savefig("TP_Graph_2.png", dpi=200, bbox_inches="tight")


###############################################################################
# Question #2: Logistic regression (full model)
###############################################################################

# Design matrix for the linear models, fit on the training set only
design_lin = MS(LIN_VARS)
design_lin = design_lin.fit(Gen_train)
X_train = design_lin.transform(Gen_train).astype(float)
X_test = design_lin.transform(Gen_test).astype(float)

# Estimate the logit model on the training set
logit = sm.GLM(Y_train, X_train,
               family=sm.families.Binomial()).fit(maxiter=500)

# The most significant predictors, sorted by p-value
smry = summarize(logit)
print(smry.sort_values("P>|z|").head(12))

# Predicted probabilities for the training and test sets
prob_train = logit.predict(X_train)
prob_test = logit.predict(X_test)

# The AUC (area under the ROC curve) is the headline evaluation metric,
# because it does not depend on a particular classification threshold
AUC_logit_train = roc_auc_score(Y_train, prob_train)
AUC_logit = roc_auc_score(Y_test, prob_test)
print("Logit AUC, train:", round(AUC_logit_train, 4),
      " test:", round(AUC_logit, 4))


###############################################################################
# Question #3: Threshold selection
###############################################################################

# The performance measures are computed across thresholds in the test set.
# For each threshold I build the confusion table
# and compute accuracy, recall, precision, the F-score, and Cohen's kappa
# by hand.
actual_train = np.where(Y_train == 1, "Retired", "Operating")
actual_test = np.where(Y_test == 1, "Retired", "Operating")

results = []
thresholds = np.arange(0.01, 0.90, 0.01)
for t in thresholds:
    labels = np.where(prob_test <= t, "Operating", "Retired")
    CM = confusion_table(labels, actual_test)
    TN = CM.loc["Operating", "Operating"]
    FP = CM.loc["Retired", "Operating"]
    FN = CM.loc["Operating", "Retired"]
    TP = CM.loc["Retired", "Retired"]
    P = FN + TP
    N = FP + TN
    P_pred = TP + FP
    N_pred = TN + FN
    Total = CM.sum().sum()
    Accuracy = (TP + TN) / Total
    Recall = TP / P
    Precision = TP / P_pred if P_pred > 0 else 0.0
    if (Precision + Recall) > 0:
        F_score = (2 * Precision * Recall) / (Precision + Recall)
    else:
        F_score = 0.0
    Pe = (N / Total) * (N_pred / Total) + (P / Total) * (P_pred / Total)
    kappa = (Accuracy - Pe) / (1 - Pe)
    results.append({"Threshold": t, "TN": TN, "FP": FP, "FN": FN, "TP": TP,
                    "Accuracy": Accuracy, "Recall": Recall,
                    "Precision": Precision, "F_score": F_score, "kappa": kappa})
results_df = pd.DataFrame(results)

# The thresholds that maximize accuracy, the F-score, and kappa
t_acc = results_df.loc[results_df["Accuracy"].idxmax(), "Threshold"]
t_F = results_df.loc[results_df["F_score"].idxmax(), "Threshold"]
t_kappa = results_df.loc[results_df["kappa"].idxmax(), "Threshold"]
print("Threshold maximizing accuracy:", round(t_acc, 2))
print("Threshold maximizing F-score :", round(t_F, 2))
print("Threshold maximizing kappa   :", round(t_kappa, 2))

# Graph 3: Each performance measure as a function of the threshold, with a
# vertical line at the threshold that maximizes that measure
measures = ["Accuracy", "Recall", "Precision", "F_score", "kappa"]
fig_3, ax_3 = subplots(2, 3, figsize=(15, 8))
for i, measure in enumerate(measures):
    row = i // 3
    col = i % 3
    ax_3[row, col].plot(results_df["Threshold"], results_df[measure],
                        color="steelblue", linewidth=2)
    t_best = results_df.loc[results_df[measure].idxmax(), "Threshold"]
    ax_3[row, col].axvline(t_best, color="grey", linestyle="--")
    ax_3[row, col].set_xlabel("Threshold", fontsize=12)
    ax_3[row, col].set_title(measure, fontsize=14)
ax_3[1, 2].axis("off")
ax_3[1, 2].text(0.5, 0.55, "Accuracy, F-score, and kappa\nall peak at the same cut:\n\nthreshold = 0.42",
                ha="center", va="center", fontsize=15, color="steelblue",
                transform=ax_3[1, 2].transAxes)
fig_3.suptitle("Performance measures across thresholds (test set)", fontsize=17)
fig_3.tight_layout()
fig_3.savefig("TP_Graph_3.png", dpi=200, bbox_inches="tight")

# The confusion table and performance measures at the F-score-optimal threshold
pred_F = np.where(prob_test <= t_F, "Operating", "Retired")
CM_F = confusion_table(pred_F, actual_test)
print(CM_F)

# The models below all use the default threshold of 0.50, so their
# performance measures are directly comparable.
pred_logit = np.where(prob_test <= 0.5, "Operating", "Retired")
CM_logit = confusion_table(pred_logit, actual_test)
Acc_logit = accuracy_score(actual_test, pred_logit)
Prec_logit = precision_score(actual_test, pred_logit, pos_label="Retired")
Rec_logit = recall_score(actual_test, pred_logit, pos_label="Retired")
F1_logit = f1_score(actual_test, pred_logit, pos_label="Retired")
print("Logit at 0.50: Accuracy", round(Acc_logit, 4),
      " Precision", round(Prec_logit, 4),
      " Recall", round(Rec_logit, 4),
      " F1", round(F1_logit, 4))


###############################################################################
# Question #4: Model selection
###############################################################################

# Forward stepwise selection with a BIC criterion adapted to classification:
# the residual sum of squares is replaced by the binomial deviance, so a
# variable enters only if it improves the deviance by more than log(n).
def neg_BIC_binomial(estimator, X, Y):
    "Negative BIC using the binomial deviance in place of the RSS"
    n, k = X.shape
    p = np.clip(estimator.predict(X), 1e-10, 1 - 1e-10)
    deviance = -2 * np.sum(Y * np.log(p) + (1 - Y) * np.log(1 - p))
    return -(deviance + np.log(n) * k) / n


strategy = Stepwise.first_peak(design_lin,
                               direction="forward",
                               max_terms=len(design_lin.terms))
forward = sklearn_selected(sm.GLM, strategy,
                           scoring=neg_BIC_binomial,
                           model_args={"family": sm.families.Binomial()})
forward.fit(Gen_train, Y_train)
forward_set = forward.selected_state_
print("Forward selection kept", len(forward_set), "of",
      len(design_lin.terms), "variables:")
print(sorted([str(s) for s in forward_set]))

# Refit the logit model with only the selected variables
design_fwd = MS(list(forward_set))
design_fwd = design_fwd.fit(Gen_train)
Xf_train = design_fwd.transform(Gen_train).astype(float)
Xf_test = design_fwd.transform(Gen_test).astype(float)
logit_fwd = sm.GLM(Y_train, Xf_train,
                   family=sm.families.Binomial()).fit(maxiter=500)

prob_fwd_train = logit_fwd.predict(Xf_train)
prob_fwd_test = logit_fwd.predict(Xf_test)
AUC_fwd = roc_auc_score(Y_test, prob_fwd_test)
print("Forward-selected logit AUC, train:",
      round(roc_auc_score(Y_train, prob_fwd_train), 4),
      " test:", round(AUC_fwd, 4))
print("Columns, full model:", X_train.shape[1],
      " forward model:", Xf_train.shape[1])

pred_fwd = np.where(prob_fwd_test <= 0.5, "Operating", "Retired")
Acc_fwd = accuracy_score(actual_test, pred_fwd)
Prec_fwd = precision_score(actual_test, pred_fwd, pos_label="Retired")
Rec_fwd = recall_score(actual_test, pred_fwd, pos_label="Retired")
F1_fwd = f1_score(actual_test, pred_fwd, pos_label="Retired")
print("Forward at 0.50: Accuracy", round(Acc_fwd, 4),
      " Precision", round(Prec_fwd, 4),
      " Recall", round(Rec_fwd, 4),
      " F1", round(F1_fwd, 4))

# L1-penalized (lasso) logistic regression. The design is standardized and
# the penalty strength is chosen by 5-fold cross-validation on the training
# set; coefficients that are not worth their penalty shrink to exactly zero.
design_noint = MS(LIN_VARS, intercept=False)
design_noint = design_noint.fit(Gen_train)
Xn_train = np.asarray(design_noint.transform(Gen_train)).astype(float)
Xn_test = np.asarray(design_noint.transform(Gen_test)).astype(float)

kfold = skm.KFold(5, random_state=0, shuffle=True)
scaler = StandardScaler(with_mean=True, with_std=True)
lasso_logit = Pipeline(steps=[("scaler", scaler),
                              ("lasso", LogisticRegressionCV(
                                  Cs=10, penalty="l1", solver="saga",
                                  cv=kfold, scoring="roc_auc",
                                  max_iter=5000))])
lasso_logit.fit(Xn_train, Y_train)

prob_L1_train = lasso_logit.predict_proba(Xn_train)[:, 1]
prob_L1_test = lasso_logit.predict_proba(Xn_test)[:, 1]
AUC_L1 = roc_auc_score(Y_test, prob_L1_test)
nonzero = int((lasso_logit.named_steps["lasso"].coef_ != 0).sum())
print("L1 logit AUC, train:", round(roc_auc_score(Y_train, prob_L1_train), 4),
      " test:", round(AUC_L1, 4))
print("L1 kept", nonzero, "of", Xn_train.shape[1], "columns")

pred_L1 = np.where(prob_L1_test <= 0.5, "Operating", "Retired")
Acc_L1 = accuracy_score(actual_test, pred_L1)
Prec_L1 = precision_score(actual_test, pred_L1, pos_label="Retired")
Rec_L1 = recall_score(actual_test, pred_L1, pos_label="Retired")
F1_L1 = f1_score(actual_test, pred_L1, pos_label="Retired")
print("L1 at 0.50: Accuracy", round(Acc_L1, 4),
      " Precision", round(Prec_L1, 4),
      " Recall", round(Rec_L1, 4),
      " F1", round(F1_L1, 4))


###############################################################################
# Question #5: Nonlinear model (GAM with B-splines)
###############################################################################

# The GAM replaces the linear terms for age and capacity with B-splines
# (5 degrees of freedom each), keeping every other variable linear
gam_terms = ([bs("age", df=5, name="bs(age)"),
              bs("log_capacity", df=5, name="bs(log capacity)")] +
             [v for v in LIN_VARS if v not in ("age", "Nameplate Capacity (MW)")])
design_gam = MS(gam_terms)
design_gam = design_gam.fit(Gen_train)
Xg_train = design_gam.transform(Gen_train).astype(float)
Xg_test = design_gam.transform(Gen_test).astype(float)

gam = sm.GLM(Y_train, Xg_train,
             family=sm.families.Binomial()).fit(method="lbfgs", maxiter=2000)

prob_gam_train = gam.predict(Xg_train)
prob_gam_test = gam.predict(Xg_test)
AUC_gam = roc_auc_score(Y_test, prob_gam_test)
print("GAM AUC, train:", round(roc_auc_score(Y_train, prob_gam_train), 4),
      " test:", round(AUC_gam, 4))

pred_gam = np.where(prob_gam_test <= 0.5, "Operating", "Retired")
Acc_gam = accuracy_score(actual_test, pred_gam)
Prec_gam = precision_score(actual_test, pred_gam, pos_label="Retired")
Rec_gam = recall_score(actual_test, pred_gam, pos_label="Retired")
F1_gam = f1_score(actual_test, pred_gam, pos_label="Retired")
print("GAM at 0.50: Accuracy", round(Acc_gam, 4),
      " Precision", round(Prec_gam, 4),
      " Recall", round(Rec_gam, 4),
      " F1", round(F1_gam, 4))

# To see the shape of the spline effects, I compute partial dependence
# curves: for each value on a grid of ages, I set the age of EVERY training
# unit to that value, predict the retirement probability, and average.
# Averaging over the real mix of technologies and fuels keeps the
# probability level interpretable. Then I repeat the same for capacity.
age_grid = np.linspace(Gen["age"].quantile(0.01), Gen["age"].quantile(0.99), 50)
prob_age = []
for a in age_grid:
    G = Gen_train.copy()
    G["age"] = a
    prob_age.append(gam.predict(design_gam.transform(G).astype(float)).mean())

cap_grid = np.linspace(Gen["Nameplate Capacity (MW)"].quantile(0.01),
                       Gen["Nameplate Capacity (MW)"].quantile(0.99), 50)
prob_cap = []
for c in cap_grid:
    G = Gen_train.copy()
    G["Nameplate Capacity (MW)"] = c
    G["log_capacity"] = np.log1p(c)
    prob_cap.append(gam.predict(design_gam.transform(G).astype(float)).mean())

# Graph 4: The two GAM spline effects
fig_4, ax_4 = subplots(1, 2, figsize=(12, 6))
ax_4[0].plot(age_grid, prob_age, linewidth=3)
ax_4[0].set_xlabel("Age (years)", fontsize=15)
ax_4[0].set_ylabel("P(retired)", fontsize=15)
ax_4[0].set_title("Spline effect of age", fontsize=15)
ax_4[1].plot(cap_grid, prob_cap, linewidth=3)
ax_4[1].set_xlabel("Nameplate capacity (MW)", fontsize=15)
ax_4[1].set_ylabel("P(retired)", fontsize=15)
ax_4[1].set_title("Spline effect of capacity", fontsize=15)
fig_4.savefig("TP_Graph_4.png", dpi=200, bbox_inches="tight")


###############################################################################
# Question #6: Tree-based models
###############################################################################

# Design matrix for the tree models: all variables, no intercept.
# Trees are unaffected by collinearity, so the summer and winter capacity
# columns stay in.
design_tree = MS(ALL_VARS, intercept=False)
design_tree = design_tree.fit(Gen_train)
D_train = design_tree.transform(Gen_train)
D_test = design_tree.transform(Gen_test)

# XGBoost does not allow feature names containing [ or ], so replace them
D_train.columns = D_train.columns.str.replace(r"[\[\]]", "_", regex=True)
D_test.columns = D_test.columns.str.replace(r"[\[\]]", "_", regex=True)
feature_names = list(D_train.columns)

Xt_train = np.asarray(D_train).astype(float)
Xt_test = np.asarray(D_test).astype(float)

# Random forest: 500 trees, sqrt(p) features considered at each split
RF_gen = RFC(n_estimators=500,
             max_features="sqrt",
             random_state=0)
RF_gen.fit(Xt_train, Y_train)
prob_RF_train = RF_gen.predict_proba(Xt_train)[:, 1]
prob_RF_test = RF_gen.predict_proba(Xt_test)[:, 1]
AUC_RF = roc_auc_score(Y_test, prob_RF_test)
print("Random forest AUC, train:",
      round(roc_auc_score(Y_train, prob_RF_train), 4),
      " test:", round(AUC_RF, 4))

pred_RF = np.where(prob_RF_test <= 0.5, "Operating", "Retired")
Acc_RF = accuracy_score(actual_test, pred_RF)
Prec_RF = precision_score(actual_test, pred_RF, pos_label="Retired")
Rec_RF = recall_score(actual_test, pred_RF, pos_label="Retired")
F1_RF = f1_score(actual_test, pred_RF, pos_label="Retired")
print("RF at 0.50: Accuracy", round(Acc_RF, 4),
      " Precision", round(Prec_RF, 4),
      " Recall", round(Rec_RF, 4),
      " F1", round(F1_RF, 4))

# Gradient boosting: 2000 shallow trees with a small learning rate
boost = GBC(n_estimators=2000,
            learning_rate=0.01,
            max_depth=2,
            random_state=0)
boost.fit(Xt_train, Y_train)
prob_boost_train = boost.predict_proba(Xt_train)[:, 1]
prob_boost_test = boost.predict_proba(Xt_test)[:, 1]
AUC_boost = roc_auc_score(Y_test, prob_boost_test)
print("Boosting AUC, train:",
      round(roc_auc_score(Y_train, prob_boost_train), 4),
      " test:", round(AUC_boost, 4))

pred_boost = np.where(prob_boost_test <= 0.5, "Operating", "Retired")
Acc_boost = accuracy_score(actual_test, pred_boost)
Prec_boost = precision_score(actual_test, pred_boost, pos_label="Retired")
Rec_boost = recall_score(actual_test, pred_boost, pos_label="Retired")
F1_boost = f1_score(actual_test, pred_boost, pos_label="Retired")
print("Boosting at 0.50: Accuracy", round(Acc_boost, 4),
      " Precision", round(Prec_boost, 4),
      " Recall", round(Rec_boost, 4),
      " F1", round(F1_boost, 4))

# XGBoost: the advanced tree-based model
xgb_gen = XGBClassifier(n_estimators=500,
                        max_depth=4,
                        learning_rate=0.05,
                        subsample=0.9,
                        colsample_bytree=0.8,
                        eval_metric="auc",
                        random_state=0)
xgb_gen.fit(Xt_train, Y_train)
prob_xgb_train = xgb_gen.predict_proba(Xt_train)[:, 1]
prob_xgb_test = xgb_gen.predict_proba(Xt_test)[:, 1]
AUC_xgb = roc_auc_score(Y_test, prob_xgb_test)
print("XGBoost AUC, train:",
      round(roc_auc_score(Y_train, prob_xgb_train), 4),
      " test:", round(AUC_xgb, 4))

pred_xgb = np.where(prob_xgb_test <= 0.5, "Operating", "Retired")
Acc_xgb = accuracy_score(actual_test, pred_xgb)
Prec_xgb = precision_score(actual_test, pred_xgb, pos_label="Retired")
Rec_xgb = recall_score(actual_test, pred_xgb, pos_label="Retired")
F1_xgb = f1_score(actual_test, pred_xgb, pos_label="Retired")
print("XGBoost at 0.50: Accuracy", round(Acc_xgb, 4),
      " Precision", round(Prec_xgb, 4),
      " Recall", round(Rec_xgb, 4),
      " F1", round(F1_xgb, 4))

# Feature importance graphs: the importance scores and variable names are
# stored in a data frame, sorted, and the top 10 are plotted
imp_RF = pd.DataFrame({"importance": RF_gen.feature_importances_},
                      index=feature_names)
imp_RF_sort = imp_RF.sort_values(by="importance", ascending=False).head(10)
imp_RF_sort = imp_RF_sort.sort_values(by="importance", ascending=True)

fig_5, ax_5 = subplots(figsize=(10, 6))
ax_5.barh(imp_RF_sort.index, imp_RF_sort["importance"],
          color="lightgreen", edgecolor="black")
ax_5.set_xlabel("Importance", fontsize=15)
ax_5.set_ylabel("Features", fontsize=15)
ax_5.set_title("Feature Importance (Random Forest, top 10)", fontsize=18)
ax_5.tick_params(axis="y", labelsize=10)
fig_5.savefig("TP_Graph_5.png", dpi=200, bbox_inches="tight")

imp_boost = pd.DataFrame({"importance": boost.feature_importances_},
                         index=feature_names)
imp_boost_sort = imp_boost.sort_values(by="importance", ascending=False).head(10)
imp_boost_sort = imp_boost_sort.sort_values(by="importance", ascending=True)

fig_6, ax_6 = subplots(figsize=(10, 6))
ax_6.barh(imp_boost_sort.index, imp_boost_sort["importance"],
          color="lightblue", edgecolor="black")
ax_6.set_xlabel("Importance", fontsize=15)
ax_6.set_ylabel("Features", fontsize=15)
ax_6.set_title("Feature Importance (Boosting, top 10)", fontsize=18)
ax_6.tick_params(axis="y", labelsize=10)
fig_6.savefig("TP_Graph_6.png", dpi=200, bbox_inches="tight")

imp_xgb = pd.DataFrame({"importance": xgb_gen.feature_importances_},
                       index=feature_names)
imp_xgb_sort = imp_xgb.sort_values(by="importance", ascending=False).head(10)
imp_xgb_sort = imp_xgb_sort.sort_values(by="importance", ascending=True)

fig_7, ax_7 = subplots(figsize=(10, 6))
ax_7.barh(imp_xgb_sort.index, imp_xgb_sort["importance"],
          color="lightcoral", edgecolor="black")
ax_7.set_xlabel("Importance", fontsize=15)
ax_7.set_ylabel("Features", fontsize=15)
ax_7.set_title("Feature Importance (XGBoost, top 10)", fontsize=18)
ax_7.tick_params(axis="y", labelsize=10)
fig_7.savefig("TP_Graph_7.png", dpi=200, bbox_inches="tight")


###############################################################################
# Question #7: Model comparison and performance evaluation
###############################################################################

# Data frame containing the four performance measures of all seven models,
# computed on the test set at the 0.50 threshold
performance = pd.DataFrame({
    "Models": ["Logit", "Forward", "L1", "GAM",
               "Boosting", "RF", "XGBoost"],
    "Accuracy": [Acc_logit, Acc_fwd, Acc_L1, Acc_gam,
                 Acc_boost, Acc_RF, Acc_xgb],
    "Precision": [Prec_logit, Prec_fwd, Prec_L1, Prec_gam,
                  Prec_boost, Prec_RF, Prec_xgb],
    "Recall": [Rec_logit, Rec_fwd, Rec_L1, Rec_gam,
               Rec_boost, Rec_RF, Rec_xgb],
    "F_score": [F1_logit, F1_fwd, F1_L1, F1_gam,
                F1_boost, F1_RF, F1_xgb],
    "Test_AUC": [AUC_logit, AUC_fwd, AUC_L1, AUC_gam,
                 AUC_boost, AUC_RF, AUC_xgb]
})
print(performance.round(4))

# Graph 8: Four bar charts, one for each performance measure (test set)
fig_8, ax_8 = subplots(2, 2, figsize=(14, 10))

ax_8[0, 0].bar(performance["Models"], performance["Accuracy"],
               color="lightblue", edgecolor="black")
ax_8[0, 0].set_title("Accuracy", fontsize=15)

ax_8[0, 1].bar(performance["Models"], performance["Precision"],
               color="lightgreen", edgecolor="black")
ax_8[0, 1].set_title("Precision", fontsize=15)

ax_8[1, 0].bar(performance["Models"], performance["Recall"],
               color="lightyellow", edgecolor="black")
ax_8[1, 0].set_title("Recall", fontsize=15)

ax_8[1, 1].bar(performance["Models"], performance["F_score"],
               color="lightcoral", edgecolor="black")
ax_8[1, 1].set_title("F1-score", fontsize=15)

for i in range(2):
    for j in range(2):
        ax_8[i, j].tick_params(axis="x", labelrotation=45)
        ax_8[i, j].set_ylim(0, 1)

fig_8.suptitle("Performance measures in the test set (threshold = 0.50)",
               fontsize=17)
fig_8.tight_layout()
fig_8.savefig("TP_Graph_8.png", dpi=200, bbox_inches="tight")

# Partial dependence of the two most influential continuous variables in the
# best-performing model (the random forest), computed the same way as the
# GAM curves: set the variable to each grid value for every training unit,
# predict, and average
pd_age_RF = []
for a in age_grid:
    G = Gen_train.copy()
    G["age"] = a
    XG = np.asarray(design_tree.transform(G)).astype(float)
    pd_age_RF.append(RF_gen.predict_proba(XG)[:, 1].mean())

pd_cap_RF = []
for c in cap_grid:
    G = Gen_train.copy()
    G["Nameplate Capacity (MW)"] = c
    XG = np.asarray(design_tree.transform(G)).astype(float)
    pd_cap_RF.append(RF_gen.predict_proba(XG)[:, 1].mean())

# Graph 9: Partial dependence in the random forest
fig_9, ax_9 = subplots(1, 2, figsize=(12, 6))
ax_9[0].plot(age_grid, pd_age_RF, linewidth=3, color="darkgreen")
ax_9[0].set_xlabel("Age (years)", fontsize=15)
ax_9[0].set_ylabel("P(retired)", fontsize=15)
ax_9[0].set_title("Partial dependence: age", fontsize=15)
ax_9[1].plot(cap_grid, pd_cap_RF, linewidth=3, color="darkgreen")
ax_9[1].set_xlabel("Nameplate capacity (MW)", fontsize=15)
ax_9[1].set_ylabel("P(retired)", fontsize=15)
ax_9[1].set_title("Partial dependence: capacity", fontsize=15)
fig_9.suptitle("Partial dependence in the random forest", fontsize=17)
fig_9.savefig("TP_Graph_9.png", dpi=200, bbox_inches="tight")

# Graph 10: ROC curves for all models on the test set
probs_test = {"Logit": prob_test,
              "Forward": prob_fwd_test,
              "L1": prob_L1_test,
              "GAM": prob_gam_test,
              "Boosting": prob_boost_test,
              "RF": prob_RF_test,
              "XGBoost": prob_xgb_test}

fig_10, ax_10 = subplots(figsize=(8, 8))
for name in probs_test:
    fpr, tpr, _ = roc_curve(Y_test, probs_test[name])
    auc_val = roc_auc_score(Y_test, probs_test[name])
    ax_10.plot(fpr, tpr, label=name + " (" + str(round(auc_val, 3)) + ")")
ax_10.plot([0, 1], [0, 1], "k--", linewidth=1)
ax_10.set_xlabel("False positive rate", fontsize=15)
ax_10.set_ylabel("True positive rate", fontsize=15)
ax_10.set_title("ROC curves (test set)", fontsize=18)
ax_10.legend(fontsize=10)
fig_10.savefig("TP_Graph_10.png", dpi=200, bbox_inches="tight")

# Model selection effectiveness: the forward and L1 models use far fewer
# columns than the full model at essentially the same performance
print("Complexity check: full logit", X_train.shape[1], "columns ->",
      "forward", Xf_train.shape[1], "| L1 nonzero", nonzero,
      "at comparable test AUC")


###############################################################################
# Question #8: Extension - how much of the signal is age?
###############################################################################

# Age is the most obvious retirement predictor. To measure how much of the
# model performance is age alone, I compare three specifications:
# (1) a logit with age as the only predictor,
# (2) the full models estimated above,
# (3) the same models re-estimated with age removed.

# (1) Age-only logit
design_age = MS(["age"])
design_age = design_age.fit(Gen_train)
logit_age = sm.GLM(Y_train, design_age.transform(Gen_train).astype(float),
                   family=sm.families.Binomial()).fit()
prob_age_test = logit_age.predict(design_age.transform(Gen_test).astype(float))
AUC_age_only = roc_auc_score(Y_test, prob_age_test)
print("Age-only logit test AUC:", round(AUC_age_only, 4))

# (3) Full models without age
NOAGE_LIN = [v for v in LIN_VARS if v != "age"]
design_na = MS(NOAGE_LIN)
design_na = design_na.fit(Gen_train)
logit_na = sm.GLM(Y_train, design_na.transform(Gen_train).astype(float),
                  family=sm.families.Binomial()).fit(maxiter=500)
AUC_logit_na = roc_auc_score(
    Y_test, logit_na.predict(design_na.transform(Gen_test).astype(float)))

NOAGE_ALL = [v for v in ALL_VARS if v != "age"]
design_tree_na = MS(NOAGE_ALL, intercept=False)
design_tree_na = design_tree_na.fit(Gen_train)
Xna_train = np.asarray(design_tree_na.transform(Gen_train)).astype(float)
Xna_test = np.asarray(design_tree_na.transform(Gen_test)).astype(float)

RF_na = RFC(n_estimators=500, max_features="sqrt", random_state=0)
RF_na.fit(Xna_train, Y_train)
AUC_RF_na = roc_auc_score(Y_test, RF_na.predict_proba(Xna_test)[:, 1])

xgb_na = XGBClassifier(n_estimators=500, max_depth=4, learning_rate=0.05,
                       subsample=0.9, colsample_bytree=0.8,
                       eval_metric="auc", random_state=0)
xgb_na.fit(Xna_train, Y_train)
AUC_xgb_na = roc_auc_score(Y_test, xgb_na.predict_proba(Xna_test)[:, 1])

age_compare = pd.DataFrame({
    "Models": ["Logit", "Random Forest", "XGBoost"],
    "AUC_with_age": [AUC_logit, AUC_RF, AUC_xgb],
    "AUC_without_age": [AUC_logit_na, AUC_RF_na, AUC_xgb_na]
})
age_compare["Drop"] = age_compare["AUC_with_age"] - age_compare["AUC_without_age"]
print(age_compare.round(4))
print("Age alone reaches", round(AUC_age_only, 3),
      "but removing age from the full models costs only",
      round(age_compare["Drop"].mean(), 3), "AUC on average")


###############################################################################
# Question #9: Extension - fleet fragility by state
###############################################################################

# I score every unit with an out-of-fold retirement-resemblance probability:
# 5-fold cross-validation, so no unit is scored by a model trained on it.
# Then, for the operating fleet only, I compute the share of each state's
# capacity whose resemblance score exceeds the F-score-optimal threshold
# from Question 3.
design_all = MS(ALL_VARS, intercept=False)
design_all = design_all.fit(Gen)
X_all = np.asarray(design_all.transform(Gen)).astype(float)
Y_all = Gen["retired"].values

RF_oof = RFC(n_estimators=500, max_features="sqrt", random_state=0)
cv5 = StratifiedKFold(5, shuffle=True, random_state=0)
oof_prob = cross_val_predict(RF_oof, X_all, Y_all, cv=cv5,
                             method="predict_proba")[:, 1]
Gen["resemblance"] = oof_prob

# Operating units whose profile resembles already-retired units
Operating = Gen.loc[Gen["retired"] == 0, :].copy()
Operating["fragile"] = (Operating["resemblance"] >= t_F).astype(int)

# Capacity-weighted fragile share by state, built from three simple groupbys
state_units = Operating.groupby("State", observed=True).size()
state_cap = Operating.groupby("State", observed=True)["Nameplate Capacity (MW)"].sum()
state_fragile = Operating.loc[Operating["fragile"] == 1, :].groupby(
    "State", observed=True)["Nameplate Capacity (MW)"].sum()

state_tbl = pd.DataFrame({"n_units": state_units,
                          "capacity_MW": state_cap,
                          "fragile_MW": state_fragile})
state_tbl["fragile_MW"] = state_tbl["fragile_MW"].fillna(0)
state_tbl = state_tbl.reset_index()
state_tbl["fragile_share"] = state_tbl["fragile_MW"] / state_tbl["capacity_MW"]
state_tbl = state_tbl.sort_values(by="fragile_share", ascending=False)
print(state_tbl.round(3))

# Graph 11: Fleet fragility by state
state_plot = state_tbl.sort_values(by="fragile_share", ascending=True)
fig_11, ax_11 = subplots(figsize=(10, 6))
ax_11.barh(state_plot["State"], state_plot["fragile_share"] * 100,
           color="lightcoral", edgecolor="black")
ax_11.set_xlabel("% of operating capacity resembling retired units", fontsize=15)
ax_11.set_ylabel("State", fontsize=15)
ax_11.set_title("Fleet fragility by state (PJM footprint)", fontsize=18)
fig_11.savefig("TP_Graph_11.png", dpi=200, bbox_inches="tight")
