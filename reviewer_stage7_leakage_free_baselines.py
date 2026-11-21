#!/usr/bin/env python3
"""Post-hoc development-internal early stopping for age-only/age+sex AFT baselines.

Selection data: only NHANES 1999-2008. Chronological internal early stop:
1999-2006 fit and 2007-2008 internal holdout. Refit on complete
1999-2008 using fixed chosen rounds; evaluate on 2009+ separately.
These baselines are POST-HOC, not originally prespecified; original
TES/full AFT comparator models may have used 2009-2012 for selection.
This is not a causal/clinical gain analysis, and no prospective claim is made.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np,pandas as pd,xgboost as xgb
from reviewer_stage1 import make_aft, concordance, c_bstrap, pred, load_booster

ERAS=['2009-2012 validation','2013-2014 audit','2015-2016 frozen confirmation','2017-2018 short-follow-up stress','NHANES III external']

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--n-boot',type=int,default=250)
    args=parser.parse_args()
    r=args.root;o=args.out;o.mkdir(parents=True,exist_ok=True)
    c=pd.read_csv(r/'data/processed/nhanes_survival_cohort.csv.gz',low_memory=False)
    dev=c[c.analysis_split.eq('train')].copy()
    inner_train=dev[dev.cycle.isin(['1999-2000','2001-2002','2003-2004','2005-2006'])].copy()
    inner_val=dev[dev.cycle.eq('2007-2008')].copy()
    assert len(dev)==24666 and len(inner_train)>10000 and len(inner_val)>1000
    assert not inner_train.participant_id.isin(inner_val.participant_id).any()
    protocol=json.loads((r/'AFT_SURVIVAL_PROTOCOL_FREEZE.json').read_text())
    params={**protocol['parameters'],'objective':'survival:aft','eval_metric':'aft-nloglik',
            'aft_loss_distribution':protocol['distribution'],'aft_loss_distribution_scale':protocol['distribution_scale'],
            'tree_method':'hist','nthread':4}
    scores={}; training=[]
    for key,cols in [('age_only',['age_years']),('age_sex',['age_years','sex_code'])]:
        print('TUNING ONLY DEVELOPMENT',key,flush=True)
        m=xgb.train(params,make_aft(inner_train,cols),num_boost_round=protocol['maximum_rounds'],
                    evals=[(make_aft(inner_val,cols),'development_2007_2008')],
                    early_stopping_rounds=protocol['early_stopping_rounds'],verbose_eval=False)
        rounds=int(m.best_iteration)+1
        print('REFIT FULL DEVELOPMENT',key,'rounds',rounds,flush=True)
        final=xgb.train(params,make_aft(dev,cols),num_boost_round=rounds,verbose_eval=False)
        f=o/f'{key}_development_tuned.ubj';final.save_model(f)
        scores[key]=(final,cols)
        training.append({'model':key+'_aft','internal_tuning_train_cycles':'1999-2006','internal_tuning_validation_cycle':'2007-2008','refit_cycles':'1999-2008','rounds':rounds,'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'post_hoc':True})
    tes,ti=load_booster(r,'outputs/tes_aft_pilot/tes_aft_model.ubj','outputs/tes_aft_pilot/TES_AFT_STATUS.json')
    features=json.loads((r/'outputs/tes_aft_pilot/TES_AFT_STATUS.json').read_text())['selected_features']
    ext_features=pd.read_csv(r/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz',low_memory=False)
    ext_mort=pd.read_fwf(r/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat',
                      colspecs=[(0,6),(14,15),(15,16),(42,45)],names=['participant_id','eligstat','event','time_months']).apply(pd.to_numeric,errors='coerce')
    ext=ext_features.merge(ext_mort,on='participant_id',how='inner',validate='one_to_one')
    ext=ext.loc[ext.eligstat.eq(1)&ext.event.notna()&ext.time_months.notna()].reset_index(drop=True)
    samples={
     ERAS[0]:c[c.analysis_split.eq('validation')],
     ERAS[1]:c[c.analysis_split.eq('calibration')],
     ERAS[2]:c[c.cycle.eq('2015-2016')],
     ERAS[3]:c[c.cycle.eq('2017-2018')],
     ERAS[4]:ext,
    }
    stats=[];boot=[]
    for idx,(era,df) in enumerate(samples.items()):
        df=df.reset_index(drop=True)
        t=df.time_months.to_numpy(float);e=df.event.to_numpy(int)
        risks={k:-m.predict(make_aft(df,cols,False)) for k,(m,cols) in scores.items()}
        risks['tes11']=-pred(tes,ti,df,features,margin=True)
        c_indexes={k:concordance(t,e,v) for k,v in risks.items()}
        for model,c_index in c_indexes.items():
            stats.append({'cohort':era,'model':model,'c_index':c_index,'n':len(df),'deaths':int(e.sum()),'development_only_tuning':model!='tes11','post_hoc_baseline':model!='tes11'})
        for a,b in [('tes11','age_sex'),('tes11','age_only'),('age_sex','age_only')]:
            x=c_bstrap(t,e,risks[a],risks[b],n_boot=args.n_boot,seed=20261122+idx*100+len(a)*3)
            boot.append({'cohort':era,'comparison':a+' minus '+b,**x,'n':len(df),'deaths':int(e.sum())})
        print(era,{key:round(v,6) for key,v in c_indexes.items()},flush=True)
    pd.DataFrame(stats).to_csv(o/'DEVELOPMENT_TUNED_AGE_BASELINE_C_INDEX_BY_ERA.csv',index=False)
    pd.DataFrame(boot).to_csv(o/'DEVELOPMENT_TUNED_BOOTSTRAP_DELTAC_95CI.csv',index=False)
    (o/'BASELINE_TRAINING_PROVENANCE.json').write_text(json.dumps({'models':training,'n_dev':len(dev),'n_inner_train':len(inner_train),'n_inner_tune':len(inner_val),'n_bootstrap':args.n_boot,'design_note':'Only development-era outcomes used for early stopping and refit. Post-hoc comparison to frozen TES; original frozen TES model itself was selected using 2009-2012 validation, so audit 2013+ is the stronger independent comparison.'},indent=2))
if __name__=='__main__':main()
