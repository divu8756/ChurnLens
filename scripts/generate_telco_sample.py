"""
Synthetic telecom churn dataset with retention offers (ChurnLens demo data).
Fixed default seed (override with env SEED) so tests are reproducible.
Churn and offer uptake follow realistic, noisy relationships so there is signal to find.
"""
import numpy as np, pandas as pd, secrets, string
import os, sys
SEED = int(os.environ.get("SEED", "20260331"))
rng = np.random.default_rng(SEED)
N = 7000
SNAPSHOT = pd.Timestamp("2026-06-30")
ch = lambda opts, p, n=N: rng.choice(opts, size=n, p=p)
yes = lambda s: (s == "Yes").astype(float)

d = pd.DataFrame()
ids = set()
while len(ids) < N:
    ids.add(f"{rng.integers(1000,9999)}-{''.join(rng.choice(list(string.ascii_uppercase),5))}")
d["customerID"] = list(rng.permutation(sorted(ids)))

# ---- demographics & account ----
d["gender"] = ch(["Male","Female"], [0.5,0.5])
age = np.clip(np.round(rng.gamma(9, 4.6, N) + rng.normal(0,3,N)), 18, 85).astype(int)
d["Age"] = age
d["SeniorCitizen"] = (age >= 60).astype(int)
d["Partner"] = np.where(rng.random(N) < np.clip(0.2 + (age-18)/80, 0.15, 0.75), "Yes", "No")
d["Dependents"] = np.where(d.Partner.eq("Yes"), ch(["Yes","No"],[0.52,0.48]), ch(["Yes","No"],[0.1,0.9]))
d["Region"] = ch(["North","South","East","West","Central"], [0.24,0.27,0.14,0.23,0.12])
d["CityTier"] = ch(["Tier 1","Tier 2","Tier 3"], [0.45,0.35,0.20])
d["SignupChannel"] = ch(["Online","Retail store","Telesales","Partner dealer"], [0.38,0.34,0.14,0.14])
contract = ch(["Month-to-month","One year","Two year"], [0.55,0.21,0.24])
d["Contract"] = contract
scale = pd.Series(contract).map({"Month-to-month":9,"One year":20,"Two year":30}).values
ten = np.clip(np.round(rng.gamma(2.0, scale) + rng.normal(0,3,N)), 1, 72).astype(int)
zero_idx = rng.choice(np.where(contract != "Month-to-month")[0], 11, replace=False)
ten[zero_idx] = 0
d["tenure"] = ten
d["NumLines"] = rng.choice([1,2,3,4], N, p=[0.62,0.22,0.11,0.05]) + (d.Dependents.eq("Yes") & (rng.random(N)<0.3)).astype(int)

# ---- services ----
d["PhoneService"] = ch(["Yes","No"], [0.9,0.1])
d["MultipleLines"] = np.where(d.PhoneService.eq("No"), "No phone service", np.where(d.NumLines>1, "Yes", ch(["Yes","No"],[0.25,0.75])))
net = np.where(d.CityTier.eq("Tier 3"), ch(["Fiber optic","DSL","No"],[0.25,0.40,0.35]), ch(["Fiber optic","DSL","No"],[0.49,0.33,0.18]))
d["InternetService"] = net
no_net = d.InternetService.eq("No")
for col,p in [("OnlineSecurity",0.37),("OnlineBackup",0.44),("DeviceProtection",0.44),("TechSupport",0.37),("StreamingTV",0.49),("StreamingMovies",0.50)]:
    d[col] = np.where(no_net, "No internet service", np.where(rng.random(N) < p, "Yes", "No"))
d["PaperlessBilling"] = np.where(rng.random(N) < np.where(age<40,0.72,0.48), "Yes", "No")
d["PaymentMethod"] = ch(["Electronic check","Mailed check","Bank transfer (automatic)","Credit card (automatic)"], [0.34,0.23,0.22,0.21])

# ---- charges ----
mc = 20 + np.where(d.PhoneService.eq("Yes"), rng.normal(5,1.5,N), 0) + np.where(d.MultipleLines.eq("Yes"), rng.normal(5,1.5,N)*np.minimum(d.NumLines,3)/1.5, 0)
mc += np.select([d.InternetService.eq("Fiber optic"), d.InternetService.eq("DSL")], [rng.normal(45,5,N), rng.normal(25,4,N)], 0)
for col in ["OnlineSecurity","OnlineBackup","DeviceProtection","TechSupport","StreamingTV","StreamingMovies"]:
    mc += np.where(d[col].eq("Yes"), rng.normal(7,2,N), 0)
d["MonthlyCharges"] = np.round(np.clip(mc + rng.normal(0,3,N), 18.25, 139.0), 2)
tc = np.maximum(d.MonthlyCharges * d.tenure * rng.normal(1.0,0.04,N), d.MonthlyCharges)
d["TotalCharges"] = np.round(tc,2).astype(str)
d.loc[d.tenure.eq(0), "TotalCharges"] = " "

# ---- usage & experience (last 3 months) ----
heavy = np.where(d.InternetService.eq("Fiber optic"), 1.6, np.where(d.InternetService.eq("DSL"), 1.0, 0.0))
data_gb = np.round(rng.gamma(2.2, 9, N) * heavy * np.where(age<35,1.4,1.0), 1)
d["AvgMonthlyDataGB"] = data_gb
latent_disengage = rng.normal(0,1,N)          # hidden dissatisfaction driver
drop = np.clip(np.round(rng.normal(-3 - 9*latent_disengage.clip(0), 12, N), 1), -95, 80)
d["DataUsageChange3mPct"] = np.where(no_net, 0.0, drop)
d["AvgMonthlyCallMinutes"] = np.round(np.clip(rng.gamma(2.5, 120, N) * np.where(d.PhoneService.eq("Yes"),1,0) * (1 - 0.1*latent_disengage.clip(0)), 0, None)).astype(int)
dcr = np.round(np.clip(rng.gamma(2, 0.9, N) + np.where(d.CityTier.eq("Tier 3"),1.2,0) + np.where(d.Region.eq("East"),0.6,0), 0, 15), 2)
d["DroppedCallRatePct"] = dcr
d["NetworkComplaints90d"] = rng.poisson(0.15 + 0.25*dcr/2)
tickets = rng.poisson(np.clip(0.4 + 0.5*latent_disengage.clip(0) + 0.3*d.InternetService.eq("Fiber optic") + 0.15*dcr, 0.05, None))
d["SupportTickets90d"] = tickets
d["AvgResolutionDays"] = np.where(tickets>0, np.round(np.clip(rng.gamma(2, 1.6, N) + np.where(d.TechSupport.eq("Yes"),-1.0,0.5), 0.2, 21),1), np.nan)
d["LatePayments12m"] = rng.poisson(np.clip(0.3 + 0.8*d.PaymentMethod.isin(["Electronic check","Mailed check"]) + 0.4*latent_disengage.clip(0), 0.05, None))
d["AppLogins30d"] = rng.poisson(np.clip((6 + 8*(age<40)) * np.exp(-0.35*latent_disengage.clip(0)), 0.2, None))
d["PlanDowngrade6m"] = np.where(rng.random(N) < 0.05 + 0.10*(latent_disengage>1), "Yes", "No")
nps = np.clip(np.round(rng.normal(7.2 - 1.3*latent_disengage.clip(0) - 0.25*d.SupportTickets90d - 0.2*dcr, 1.8)), 0, 10)
d["NPS"] = np.where(rng.random(N) < 0.38, np.nan, nps)   # ~38% never answered the survey

# ---- churn propensity before any offer (the "true" risk) ----
z0 = (-1.85
      + np.select([d.Contract.eq("Month-to-month"), d.Contract.eq("One year")], [1.25, 0.0], -1.35)
      - 0.03*d.tenure
      + 0.7*d.InternetService.eq("Fiber optic") - 0.8*no_net
      + 0.4*d.PaymentMethod.eq("Electronic check")
      - 0.4*yes(d.OnlineSecurity) - 0.35*yes(d.TechSupport)
      + 0.2*yes(d.PaperlessBilling) + 0.2*d.SeniorCitizen - 0.15*yes(d.Dependents)
      + 0.010*(d.MonthlyCharges-65)
      - 0.012*d.DataUsageChange3mPct.clip(-60,30)
      + 0.18*d.SupportTickets90d + 0.25*d.NetworkComplaints90d
      + 0.06*dcr + 0.12*d.LatePayments12m
      - 0.04*d.AppLogins30d.clip(0,20)
      + 0.5*yes(d.PlanDowngrade6m) - 0.12*(d.NumLines-1)
      + 0.55*latent_disengage.clip(0)
      + rng.normal(0,0.6,N))

# ---- retention campaign (Q1 2026) ----
# the operator's old CRM score targets riskier customers (selection bias), plus randomness
crm_score = 1/(1+np.exp(-(z0 + rng.normal(0,0.9,N))))
targeted = rng.random(N) < np.clip(0.08 + 0.75*crm_score, 0, 0.9)
targeted &= d.tenure.values > 0
holdout = targeted & (rng.random(N) < 0.25)            # random control group, no offer
offered = targeted & ~holdout

offers = {
  "10% loyalty discount (3 mo)":   dict(cost=lambda mc: 0.30*mc, w=0.26),
  "Free 10GB data booster":         dict(cost=lambda mc: 6.0+0*mc, w=0.20),
  "1 month free on annual plan":    dict(cost=lambda mc: 1.0*mc, w=0.18),
  "Free OTT streaming (6 mo)":      dict(cost=lambda mc: 18.0+0*mc, w=0.16),
  "Priority tech support (6 mo)":   dict(cost=lambda mc: 5.0+0*mc, w=0.12),
  "Device upgrade credit":          dict(cost=lambda mc: 45.0+0*mc, w=0.08),
}
names = list(offers); w = np.array([offers[k]["w"] for k in names]); w/=w.sum()
offer = np.full(N, "", dtype=object)
offer[offered] = rng.choice(names, offered.sum(), p=w)
d["CampaignGroup"] = np.where(offered, "Offer sent", np.where(holdout, "Holdout (no offer)", "Not targeted"))
d["OfferShown"] = offer
d["OfferChannel"] = np.where(offered, ch(["SMS","App push","Outbound call","Email"],[0.40,0.25,0.20,0.15]), "")
start, end = pd.Timestamp("2026-01-05"), pd.Timestamp("2026-03-27")
days = rng.integers(0, (end-start).days+1, N)
d["OfferDate"] = np.where(targeted, (start + pd.to_timedelta(days, unit="D")).strftime("%Y-%m-%d"), "")

mcv = d.MonthlyCharges.values
streamer = (yes(d.StreamingTV)+yes(d.StreamingMovies)).values > 0
heavy_user = d.AvgMonthlyDataGB.values > np.nanpercentile(d.AvgMonthlyDataGB[d.AvgMonthlyDataGB>0], 60)
mtm = (d.Contract=="Month-to-month").values
many_tickets = d.SupportTickets90d.values >= 2
# relevance drives click & accept
rel = np.zeros(N)
for i_name in names:
    m = offer == i_name
    if i_name.startswith("10%"): rel[m] = 0.5 + 0.5*(mcv[m] > 75)
    elif "data booster" in i_name: rel[m] = 0.2 + 0.8*heavy_user[m]
    elif "annual" in i_name: rel[m] = 0.2 + 0.6*mtm[m]
    elif "OTT" in i_name: rel[m] = 0.2 + 0.7*streamer[m]
    elif "Priority" in i_name: rel[m] = 0.2 + 0.7*many_tickets[m]
    else: rel[m] = 0.35
chan_boost = pd.Series(d.OfferChannel).map({"SMS":0.0,"App push":0.3,"Outbound call":0.6,"Email":-0.3,"":0}).values
p_click = 1/(1+np.exp(-(-1.3 + 2.2*rel + chan_boost + 0.03*d.AppLogins30d.clip(0,20).values + rng.normal(0,0.5,N))))
clicked = offered & (rng.random(N) < p_click)
p_acc = 1/(1+np.exp(-(-0.9 + 1.8*rel + 0.3*chan_boost + rng.normal(0,0.5,N))))
accepted = clicked & (rng.random(N) < p_acc)
d["OfferClicked"] = np.where(offered, np.where(clicked,"Yes","No"), "")
d["OfferAccepted"] = np.where(offered, np.where(accepted,"Yes","No"), "")
cost = np.zeros(N)
for k in names:
    m = accepted & (offer == k)
    cost[m] = offers[k]["cost"](mcv[m])
d["OfferCost"] = np.where(offered, np.where(accepted, np.round(cost,2).astype(str), "0"), "")

# ---- true offer effect on churn (heterogeneous, only if accepted) ----
eff = np.zeros(N)
for k in names:
    m = accepted & (offer == k)
    if k.startswith("10%"): eff[m] = -0.55 - 0.60*(mcv[m] > 75)
    elif "data booster" in k: eff[m] = -0.20 - 0.95*heavy_user[m]
    elif "annual" in k: eff[m] = -0.45 - 1.00*mtm[m]
    elif "OTT" in k: eff[m] = -0.10 - 0.85*streamer[m]
    elif "Priority" in k: eff[m] = -0.20 - 0.95*many_tickets[m]
    else: eff[m] = -0.10
eff[accepted] += rng.normal(0, 0.25, accepted.sum())      # individual variation
z = z0 + eff
churn = (rng.random(N) < 1/(1+np.exp(-z))) & (d.tenure.values > 0)
d["Churn"] = np.where(churn, "Yes", "No")

# ---- light real-world messiness for the cleaning step ----
def mess(col, frac, fn):
    idx = rng.choice(N, int(frac*N), replace=False); d.loc[idx, col] = d.loc[idx, col].map(fn)
mess("InternetService", 0.004, lambda s: s.lower() if s!="No" else s)
mess("PaymentMethod", 0.003, lambda s: " "+s+" ")
nan_idx = rng.choice(np.where(~no_net)[0], 60, replace=False); d.loc[nan_idx, "AvgMonthlyDataGB"] = np.nan
neg_idx = rng.choice(np.where(d.AvgMonthlyCallMinutes>0)[0], 5, replace=False); d.loc[neg_idx, "AvgMonthlyCallMinutes"] *= -1
dups = d[d.tenure>0].sample(14, random_state=int(rng.integers(1e9)))
d = pd.concat([d, dups]).sample(frac=1, random_state=int(rng.integers(1e9))).reset_index(drop=True)

d["SnapshotDate"] = SNAPSHOT.strftime("%Y-%m-%d")
out = sys.argv[1] if len(sys.argv) > 1 else "backend/sample_data/telco_churn.csv"
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
d.to_csv(out, index=False)
print("seed", SEED, "rows", len(d))
