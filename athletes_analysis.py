# pip install pandas seaborn matplotlib pyarrow
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

sns.set_theme(style="whitegrid", context="talk")

# ------------------------------------------------------------------
# CONFIG: run once, look at the printed columns, then adjust names
# ------------------------------------------------------------------
FILE = "before_raw_data.xlsx"
COL_BORN = "born_date"
COL_CITY = "born_city"
COL_REGION = "born_region"
COL_COUNTRY = "NOC"          # country name column (e.g. France, Great Britain)
COL_HEIGHT = "height_cm"
COL_WEIGHT = "weight_kg"
COL_DIED = "died_date"

# ------------------------------------------------------------------
# 1. LOAD
# ------------------------------------------------------------------
df = pd.read_excel(FILE)          # engine="pyarrow" is used automatically
df.columns = df.columns.str.strip()
print("Shape:", df.shape)
print("Columns:", list(df.columns))
print(df.dtypes, "\n")
print(df.head(), "\n")

# ------------------------------------------------------------------
# 2. DATA CLEANING & MISSING VALUES
# ------------------------------------------------------------------
# 2a. Drop fully empty rows
df = df.dropna(how="all").copy()

# 2b. Parse dates (handles datetime columns and mixed text formats)
for c in (COL_BORN, COL_DIED):
    if not pd.api.types.is_datetime64_any_dtype(df[c]):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")

# 2c. Numeric height/weight (bad values become NaN)
for c in (COL_HEIGHT, COL_WEIGHT):
    df[c] = pd.to_numeric(df[c], errors="coerce")

# 2d. Missing value report BEFORE handling
def missing_report(data, title):
    rep = pd.DataFrame({
        "missing_count": data.isna().sum(),
        "missing_pct": (data.isna().mean() * 100).round(2),
        "non_missing": data.notna().sum(),
    }).sort_values("missing_pct", ascending=False)
    print(f"\n=== {title} ===")
    print(rep)
    return rep

rep_before = missing_report(df, "MISSING VALUES (before handling)")

plt.figure(figsize=(10, 6))
ax = sns.barplot(x=rep_before["missing_pct"], y=rep_before.index,
                 hue=rep_before.index, palette="Reds_r", legend=False)
for container in ax.containers:
    ax.bar_label(container, fmt="%.1f%%", padding=3, fontsize=11)
ax.set(xlabel="Missing (%)", ylabel="", xlim=(0, 105),
       title="Missing Data by Column")
sns.despine()
plt.tight_layout()
plt.savefig("01_missing_values.png", dpi=200)
plt.show()

# 2e. Impossible values -> NaN (treated as missing)
df.loc[~df[COL_HEIGHT].between(120, 250), COL_HEIGHT] = np.nan
df.loc[~df[COL_WEIGHT].between(30, 220), COL_WEIGHT] = np.nan
df.loc[(df[COL_BORN] < "1800-01-01") | (df[COL_BORN] > pd.Timestamp.today()),
       COL_BORN] = pd.NaT

# 2f. HANDLING STRATEGY
#  - text columns: "Unknown"
#  - died_date: blank usually = alive / not recorded -> keep NaT + flag
#  - birth_year: derived, NOT imputed
#  - height/weight: originals kept for analysis (real pairs only);
#    *_filled = country median, then global median, with *_imputed flags
for c in (COL_CITY, COL_REGION, COL_COUNTRY):
    df[c] = df[c].fillna("Unknown").astype(str).str.strip()

df["is_deceased"] = df[COL_DIED].notna()
df["birth_year"] = df[COL_BORN].dt.year

for col in (COL_HEIGHT, COL_WEIGHT):
    df[f"{col}_imputed"] = df[col].isna()
    country_median = df.groupby(COL_COUNTRY)[col].transform("median")
    df[f"{col}_filled"] = df[col].fillna(country_median).fillna(df[col].median())

missing_report(
    df[[COL_HEIGHT, COL_WEIGHT, f"{COL_HEIGHT}_filled", f"{COL_WEIGHT}_filled",
        "birth_year", COL_COUNTRY]],
    "MISSING VALUES (after handling)",
)

# ------------------------------------------------------------------
# 3. TOP 10 COUNTRIES BY NUMBER OF ATHLETES
# ------------------------------------------------------------------
known = df[df[COL_COUNTRY] != "Unknown"]
top10 = known[COL_COUNTRY].value_counts().head(10).reset_index()
top10.columns = ["country", "athletes"]
print("\n=== TOP 10 COUNTRIES ===")
print(top10)

plt.figure(figsize=(12, 7))
ax = sns.barplot(data=top10, x="athletes", y="country",
                 hue="country", palette="viridis", legend=False)
for container in ax.containers:
    ax.bar_label(container, padding=4, fontsize=12)
ax.set(title="Top 10 Countries by Number of Athletes",
       xlabel="Number of Athletes", ylabel="")
sns.despine()
plt.tight_layout()
plt.savefig("02_top10_countries.png", dpi=200)
plt.show()

# ------------------------------------------------------------------
# 4. HEIGHT vs WEIGHT
# ------------------------------------------------------------------
hw = df.dropna(subset=[COL_HEIGHT, COL_WEIGHT]).copy()   # real pairs only
print(f"\nAthletes with both height and weight: {len(hw)} of {len(df)}")

pearson = hw[COL_HEIGHT].corr(hw[COL_WEIGHT])
spearman = hw[COL_HEIGHT].corr(hw[COL_WEIGHT], method="spearman")
slope, intercept = np.polyfit(hw[COL_HEIGHT], hw[COL_WEIGHT], 1)
print(f"Pearson r  = {pearson:.3f}")
print(f"Spearman r = {spearman:.3f}")
print(f"Trend: weight = {slope:.2f} * height + {intercept:.2f} "
      f"(~{slope:.2f} kg per extra cm)")

# 4a. Overall scatter + regression line
plt.figure(figsize=(11, 8))
ax = sns.regplot(data=hw, x=COL_HEIGHT, y=COL_WEIGHT,
                 scatter_kws={"alpha": 0.35, "s": 25},
                 line_kws={"color": "crimson", "lw": 2.5})
ax.set(title=f"Height vs Weight (Pearson r = {pearson:.2f}, n = {len(hw):,})",
       xlabel="Height (cm)", ylabel="Weight (kg)")
plt.tight_layout()
plt.savefig("03_height_weight_overall.png", dpi=200)
plt.show()

# 4b. Country-wise (top 8 countries with enough complete data)
MIN_N = 30
counts = hw[COL_COUNTRY].value_counts()
eligible = counts[counts >= MIN_N].head(8).index.tolist()
hw_top = hw[hw[COL_COUNTRY].isin(eligible)]

plt.figure(figsize=(12, 8))
ax = sns.scatterplot(data=hw_top, x=COL_HEIGHT, y=COL_WEIGHT,
                     hue=COL_COUNTRY, alpha=0.6, s=40)
ax.set(title="Height vs Weight by Country",
       xlabel="Height (cm)", ylabel="Weight (kg)")
sns.move_legend(ax, "upper left", bbox_to_anchor=(1.02, 1), title="Country")
plt.tight_layout()
plt.savefig("04_height_weight_by_country_overlay.png", dpi=200)
plt.show()

g = sns.lmplot(data=hw_top, x=COL_HEIGHT, y=COL_WEIGHT, col=COL_COUNTRY,
               col_wrap=4, height=3.5,
               scatter_kws={"alpha": 0.4, "s": 15},
               line_kws={"color": "crimson"})
g.set_axis_labels("Height (cm)", "Weight (kg)")
g.figure.suptitle("Height-Weight Relationship per Country", y=1.03)
g.savefig("05_height_weight_per_country.png", dpi=200)
plt.show()

# Country summary table
country_stats = (
    hw[hw[COL_COUNTRY].isin(counts[counts >= MIN_N].index)]
    .groupby(COL_COUNTRY)
    .apply(lambda d: pd.Series({
        "n": len(d),
        "mean_height": d[COL_HEIGHT].mean(),
        "mean_weight": d[COL_WEIGHT].mean(),
        "correlation": d[COL_HEIGHT].corr(d[COL_WEIGHT]),
        "kg_per_cm": np.polyfit(d[COL_HEIGHT], d[COL_WEIGHT], 1)[0],
    }), include_groups=False)
    .round(2)
    .sort_values("mean_height", ascending=False)
)
print(f"\n=== COUNTRY STATS (>= {MIN_N} complete records) ===")
print(country_stats)

# Boxplots by country
order = (hw_top.groupby(COL_COUNTRY)[COL_HEIGHT].median()
         .sort_values(ascending=False).index)
fig, axes = plt.subplots(1, 2, figsize=(16, 7))
sns.boxplot(data=hw_top, y=COL_COUNTRY, x=COL_HEIGHT, order=order,
            hue=COL_COUNTRY, palette="Set2", legend=False, ax=axes[0])
axes[0].set(title="Height by Country", xlabel="Height (cm)", ylabel="")
sns.boxplot(data=hw_top, y=COL_COUNTRY, x=COL_WEIGHT, order=order,
            hue=COL_COUNTRY, palette="Set2", legend=False, ax=axes[1])
axes[1].set(title="Weight by Country", xlabel="Weight (kg)", ylabel="")
plt.tight_layout()
plt.savefig("06_height_weight_boxplots.png", dpi=200)
plt.show()

# ------------------------------------------------------------------
# 5. BIRTH YEAR TRENDS
# ------------------------------------------------------------------
by = df["birth_year"].dropna().astype(int)
print(f"\nBirth years available: {len(by)} of {len(df)}")
print(by.describe())
peak_decade = (by // 10 * 10).value_counts().idxmax()
print(f"Most represented decade: {peak_decade}s")

# 5a. Histogram + KDE
plt.figure(figsize=(13, 7))
ax = sns.histplot(by, binwidth=5, kde=True, color="#3b6ea5", edgecolor="white")
ax.axvline(by.median(), color="crimson", ls="--", lw=2,
           label=f"Median: {int(by.median())}")
ax.set(title="Distribution of Athlete Birth Years",
       xlabel="Birth Year", ylabel="Number of Athletes")
ax.legend()
plt.tight_layout()
plt.savefig("07_birth_year_hist_kde.png", dpi=200)
plt.show()

# 5b. Athletes per birth decade
decade = (by // 10 * 10).value_counts().sort_index().reset_index()
decade.columns = ["decade", "athletes"]
plt.figure(figsize=(13, 6))
ax = sns.barplot(data=decade, x="decade", y="athletes",
                 hue="decade", palette="mako", legend=False)
ax.bar_label(ax.containers[0], fontsize=10, padding=2)
ax.set(title="Athletes by Birth Decade", xlabel="Birth Decade",
       ylabel="Number of Athletes")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("08_birth_decade_bar.png", dpi=200)
plt.show()

# 5c. KDE of birth year, top 5 countries
top5 = top10["country"].head(5).tolist()
plt.figure(figsize=(13, 7))
ax = sns.kdeplot(data=df[df[COL_COUNTRY].isin(top5)], x="birth_year",
                 hue=COL_COUNTRY, fill=True, common_norm=False,
                 alpha=0.25, linewidth=2)
ax.set(title="Birth Year Density: Top 5 Countries", xlabel="Birth Year")
plt.tight_layout()
plt.savefig("09_birth_year_kde_by_country.png", dpi=200)
plt.show()

# ------------------------------------------------------------------
# 6. SAVE CLEANED DATA
# ------------------------------------------------------------------
df.to_excel("bios_cleaned.xlsx", index=False)
print("\nDone. Charts saved as PNGs, cleaned data saved to bios_cleaned.parquet")
