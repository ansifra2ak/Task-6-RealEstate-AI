"""Strict, reproducible ingestion and train-only preprocessing. No model fitting."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.services.datasets import audit_csv, dataset_status

ID, TARGET = 'Property_ID', 'Price'
NUM = ['Area', 'Bedrooms', 'Bathrooms', 'Age']
CAT = ['Location', 'Property_Type']
RAW = NUM + CAT
DERIVED = ['Area_per_bedroom', 'Bathrooms_per_bedroom']
SEED = 42


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def validate_properties(frame):
    expected = [ID, *RAW, TARGET]
    if set(frame.columns) != set(expected) or len(frame.columns) != len(expected):
        raise ValueError('Property schema mismatch: expected ' + ', '.join(expected))
    df = frame[expected].copy()
    if df.empty or df.isna().any().any():
        raise ValueError('Empty property dataset or missing value; review source, no silent imputation')
    for col in [ID, *CAT]:
        df[col] = df[col].astype(str).str.strip()
        if df[col].eq('').any():
            raise ValueError(f'Blank {col}')
    for col in [*NUM, TARGET]:
        df[col] = pd.to_numeric(df[col], errors='raise')
        if not np.isfinite(df[col]).all():
            raise ValueError(f'Non-finite {col}')
    if df[ID].duplicated().any() or df.duplicated().any():
        raise ValueError('Duplicate property identifiers or records')
    if df[RAW].duplicated().any():
        raise ValueError('Duplicate feature profiles: review/group before splitting')
    if (df[['Area', 'Bedrooms', 'Bathrooms', TARGET]] <= 0).any().any() or (df['Age'] < 0).any():
        raise ValueError('Nonpositive area/rooms/price or negative age')
    for col in ['Bedrooms', 'Bathrooms', 'Age']:
        if (df[col] % 1 != 0).any():
            raise ValueError(f'Nonintegral {col}')
    return df.sort_values(ID).reset_index(drop=True)


def features(df):
    x = df[RAW].copy()
    if (x['Bedrooms'] <= 0).any():
        raise ValueError('Bedrooms must be positive')
    x['Area_per_bedroom'] = x['Area'] / x['Bedrooms']
    x['Bathrooms_per_bedroom'] = x['Bathrooms'] / x['Bedrooms']
    return x


def split_properties(df):
    df = df.sort_values(ID).reset_index(drop=True)
    train, hold = train_test_split(df, test_size=0.30, random_state=SEED)
    val, test = train_test_split(hold, test_size=0.50, random_state=SEED)
    return {k: v.sort_values(ID).reset_index(drop=True) for k, v in [('train', train), ('validation', val), ('test', test)]}


def make_preprocessor():
    return ColumnTransformer([('numeric', StandardScaler(), NUM + DERIVED),
                              ('categorical', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CAT)],
                             remainder='drop', verbose_feature_names_out=True)


def plot_training(train, out):
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'figure.facecolor': 'white'})
    blue, teal = '#285e89', '#16877e'
    def save(name, title, draw):
        fig, ax = plt.subplots(figsize=(9, 5.5))
        draw(ax)
        ax.set_title(title, loc='left', pad=15)
        fig.text(.12, .025, f'Training partition only (n={len(train)}); currency and area units unspecified.', fontsize=9, color='#48596a')
        fig.tight_layout(rect=[0, .055, 1, 1])
        fig.savefig(out/name, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
    def hist(ax):
        ax.hist(train.Price/1e6, bins=15, color=blue, edgecolor='white')
        ax.axvline(train.Price.median()/1e6, color=teal, linestyle='--', label='Median')
        ax.set(xlabel='Recorded price (million source units)', ylabel='Properties'); ax.legend(frameon=False)
    def scatter(ax):
        ax.scatter(train.Area, train.Price/1e6, color=teal, alpha=.65, s=28)
        ax.set(xlabel='Area (source units)', ylabel='Recorded price (million source units)')
    def category(ax,col):
        g = train.groupby(col).Price.agg(['median','size']).sort_values('median')
        bars = ax.barh(g.index, g['median']/1e6, color=blue)
        ax.bar_label(bars, labels=[f'{v/1e6:.2f} (n={n})' for v,n in zip(g['median'],g['size'])], padding=4, fontsize=9)
        ax.set_xlim(0, max(g['median']/1e6)*1.35); ax.set_xlabel('Median recorded price (million source units)')
    def heat(ax):
        c = train[NUM+[TARGET]].corr()
        im = ax.imshow(c, cmap='RdBu_r', vmin=-1, vmax=1)
        ax.set_xticks(range(len(c)), c.columns, rotation=30, ha='right'); ax.set_yticks(range(len(c)),c.columns)
        for i in range(len(c)):
            for j in range(len(c)):
                ax.text(j,i,f'{c.iloc[i,j]:.2f}',ha='center',va='center',color='white' if abs(c.iloc[i,j])>.55 else '#233142')
        ax.figure.colorbar(im,ax=ax,shrink=.8,label='Pearson r')
    save('price_distribution.png','Distribution of property prices',hist)
    save('area_vs_price.png','Property area versus recorded price',scatter)
    save('location_analysis.png','Median property price by location',lambda ax:category(ax,'Location'))
    save('property_type_analysis.png','Median property price by property type',lambda ax:category(ax,'Property_Type'))
    save('correlation_heatmap.png','Numeric feature correlations',heat)


def prepare(root=ROOT):
    root = Path(root)
    statuses = dataset_status(root)
    if any(s['status']!='verified' for s in statuses):
        raise ValueError('Original dataset hash mismatch or missing file; restore original CSVs')
    audits = {}
    for s in statuses:
        a = audit_csv(root/'data/raw'/s['name'])
        if a['malformed_rows'] or a['rows'] != s['rows'] or len(a['columns']) != s['columns']:
            raise ValueError('Malformed CSV or manifest mismatch: '+s['name'])
        audits[s['name']] = {**a, 'role':s['role'], 'integrity':s['status']}
    raw = root/'data/raw/house_prices.csv'
    df = validate_properties(pd.read_csv(raw))
    parts = split_properties(df)
    train = parts['train']
    proc = make_preprocessor().fit(features(train))
    names = list(proc.get_feature_names_out())
    out, reports, viz = root/'data/processed', root/'reports', root/'visualizations'
    for p in [out,reports,viz]: p.mkdir(parents=True,exist_ok=True)
    df.to_csv(out/'cleaned_properties.csv',index=False)
    for name, part in parts.items():
        part.to_csv(out/f'{name}.csv',index=False)
        transformed = pd.DataFrame(proc.transform(features(part)),columns=names)
        transformed.insert(0,ID,part[ID]); transformed[TARGET]=part[TARGET]
        transformed.to_csv(out/f'{name}_features.csv',index=False)
    joblib.dump(proc,out/'preprocessor.joblib')
    write_json(out/'split_manifest.json',{'seed':SEED,'source_sha256':sha(raw),'strategy':'random split sorted by ID; no dates available','partitions':{k:{'rows':len(v),'sha256':sha(out/f'{k}.csv')} for k,v in parts.items()}})
    write_json(reports/'data_quality.json',{'datasets':audits,'property_validation':'passed','property_unique_ids':int(df[ID].nunique()),'duplicate_feature_profiles':int(df[RAW].duplicated().sum()),'rows_removed':0,'units':'currency and area units unspecified','reference_datasets':'inventory only; never joined'})
    write_json(reports/'preprocessing_report.json',{'source_sha256':sha(raw),'seed':SEED,'split_counts':{k:len(v) for k,v in parts.items()},'raw_features':RAW,'derived_features':DERIVED,'excluded_predictors':[ID,TARGET],'transformed_feature_count':len(names),'transformed_features':names,'fit_partition':'train only','numeric_scaler':'StandardScaler','categorical_encoder':'OneHotEncoder(handle_unknown=ignore)','unseen_categories':{k:{c:sorted(set(v[c])-set(train[c])) for c in CAT} for k,v in parts.items()},'missing_policy':'reject invalid rows; no imputation required for supplied data','phase3_rule':'Fit preprocessing afresh within each cross-validation fold using raw training features; choose on training/validation only; evaluate test once. Do not train on test_features.csv.'})
    plot_training(train,viz)
    stats = train[TARGET].describe()
    corr = train[NUM+[TARGET]].corr()[TARGET].drop(TARGET)
    lines = ['# Phase 2 — Exploratory data analysis','',f'Original property records: {len(df)}. Training-only EDA: {len(train)} records. Validation and held-out test: {len(parts["validation"])} each. No model trained.','', '## Training price statistics (source units, currency unspecified)','', '| Statistic | Value |','|---|---:|']
    lines += [f'| {k} | {stats[k]:,.2f} |' for k in ['min','25%','50%','mean','75%','max','std']]
    lines += ['', '## Training numeric correlations with Price','', '| Feature | Pearson r |','|---|---:|'] + [f'| {k} | {v:.4f} |' for k,v in corr.items()]
    lines += ['', '## Interpretation and limitations', '', 'Correlation is descriptive, not causal. Category comparisons are unadjusted. The dataset is small and has no transaction dates, verified currency, area units, sampling frame or geographic detail beyond the provided categories. No claim of current market value. No target-derived feature (including price per area) is used. No unrelated datasets are joined. No outlier was removed automatically. Future model selection must not inspect held-out test outcomes.']
    (reports/'eda_summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return {'rows':len(df),'splits':{k:len(v) for k,v in parts.items()},'features':len(names),'source_sha256':sha(raw)}
