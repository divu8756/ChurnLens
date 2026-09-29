"""
ChurnLens India demo dataset (synthetic). Fixed default seed (override with env SEED).
Outputs (in ./churnlens_india_dataset/):
  customers.csv          one row per customer: profile, device, network, money, care & offer
                         aggregates, and churn outcome (+ post-churn reason columns)
  monthly_usage.csv      12 months of history per customer (Apr 2025 - Mar 2026)
  care_interactions.csv  every care contact in the 12 months
  offer_history.csv      every retention offer across 3 campaigns
Timeline: features observed up to SNAPSHOT (2026-03-31); churn measured 2026-04-01..2026-06-29 (90 days).
"""
import numpy as np, pandas as pd, secrets, string, os
import sys
SEED = int(os.environ.get("SEED", "20260401")); rng = np.random.default_rng(SEED)
N = 7000
SNAP = pd.Timestamp("2026-03-31"); WIN_END = SNAP + pd.Timedelta(days=90)
MONTHS = pd.period_range("2025-04", "2026-03", freq="M")
OUT = sys.argv[1] if len(sys.argv) > 1 else "backend/sample_data/india"; os.makedirs(OUT, exist_ok=True)
ch = lambda o, p, n=N: rng.choice(o, size=n, p=np.array(p)/np.sum(p))
sig = lambda x: 1/(1+np.exp(-x))

# ---------------- customer master ----------------
ids = set()
while len(ids) < N: ids.add("C" + "".join(rng.choice(list(string.digits), 7)))
c = pd.DataFrame({"CustomerID": sorted(ids)}); c = c.sample(frac=1, random_state=int(rng.integers(1e9))).reset_index(drop=True)
circles = {  # circle: (weight, pincode first digits, zone)
 "Delhi":(7,"11","North"),"Mumbai":(6,"40","West"),"Kolkata":(4,"70","East"),"Maharashtra & Goa":(8,"41","West"),
 "Karnataka":(7,"56","South"),"Tamil Nadu":(7,"60","South"),"Kerala":(4,"68","South"),"Andhra Pradesh & Telangana":(8,"50","South"),
 "Gujarat":(6,"38","West"),"Rajasthan":(5,"30","North"),"UP East":(8,"22","North"),"UP West":(6,"24","North"),
 "Bihar & Jharkhand":(7,"80","East"),"West Bengal":(5,"71","East"),"Madhya Pradesh & Chhattisgarh":(6,"45","Central"),
 "Punjab":(3,"14","North"),"Haryana":(3,"12","North"),"Odisha":(3,"75","East"),"Assam":(2,"78","North East"),
 "North East":(1,"79","North East"),"Himachal Pradesh":(1,"17","North"),"Jammu & Kashmir":(1,"18","North")}
cn = list(circles); cw = [circles[k][0] for k in cn]
c["Circle"] = ch(cn, cw)
c["Zone"] = c.Circle.map({k:v[2] for k,v in circles.items()})
c["Pincode"] = [circles[x][1] + f"{rng.integers(0,10000):04d}" for x in c.Circle]
metro = c.Circle.isin(["Delhi","Mumbai","Kolkata"])
c["UrbanRural"] = np.where(metro, ch(["Urban","Semi-urban"],[0.9,0.1]), ch(["Urban","Semi-urban","Rural"],[0.35,0.30,0.35]))
rural = (c.UrbanRural=="Rural").values
c["Gender"] = ch(["Male","Female"],[0.58,0.42])
age = np.clip(np.round(rng.gamma(7.5, 4.6, N)+ rng.normal(0,3,N)), 18, 80).astype(int); c["Age"] = age
c["PlanType"] = np.where(rng.random(N) < np.where(metro,0.30,0.14), "Postpaid", "Prepaid")
post = (c.PlanType=="Postpaid").values; pre = ~post
c["AcquisitionChannel"] = ch(["Retail store","Online","Distributor/retailer","MNP port-in","Telesales"],[0.34,0.18,0.30,0.12,0.06])
ten = np.clip(np.round(rng.gamma(1.6, 22, N)), 1, 180).astype(int)
c["TenureMonths"] = ten
c["ActivationDate"] = (SNAP - pd.to_timedelta(ten*30.4 + rng.integers(0,30,N), unit="D")).strftime("%Y-%m-%d")
lock = np.where(post & (rng.random(N)<0.55), rng.choice([12,24],N,p=[0.6,0.4]), 0)
cycle_end = np.where(lock>0, lock*np.ceil((ten+0.5)/np.maximum(lock,1)), np.nan)
days_to_end = np.where(lock>0, np.round((cycle_end - ten)*30.4 - rng.integers(0,30,N)), np.nan)
days_to_end = np.where(lock>0, np.maximum(days_to_end, 1), np.nan)
c["LockInMonths"] = np.where(post, lock, np.nan)
c["ContractEndDate"] = [ (SNAP + pd.Timedelta(days=int(x))).strftime("%Y-%m-%d") if not np.isnan(x) else "" for x in days_to_end]
c["DaysToContractEnd"] = days_to_end

# household / convergence
c["FamilyPlanMembers"] = np.where(post, rng.choice([1,2,3,4],N,p=[0.55,0.22,0.15,0.08]), 1)
c["HomeFiber"] = np.where(rng.random(N) < np.where(rural,0.03,0.16) + 0.12*post, "Yes","No")
c["DTH"] = np.where(rng.random(N) < 0.18 + 0.10*(c.HomeFiber=="Yes"), "Yes","No")
c["ConvergedBundle"] = np.where((c.HomeFiber=="Yes") & (rng.random(N)<0.55), "Yes","No")

# device
tier = np.where(rng.random(N) < 0.20+0.25*post, "Premium", np.where(rng.random(N)<0.55,"Mid","Budget"))
c["HandsetTier"] = tier
c["DeviceAgeMonths"] = np.clip(np.round(rng.gamma(2.2, 11, N)),0,96).astype(int)
p5g = np.select([tier=="Premium", tier=="Mid"], [0.92,0.62], 0.28) * np.where(c.DeviceAgeMonths>36,0.35,1)
c["Is5GDevice"] = np.where(rng.random(N)<p5g,"Yes","No")
c["DualSIM"] = np.where(rng.random(N) < 0.88, "Yes","No")
secondary = (c.DualSIM=="Yes").values & (rng.random(N) < np.where(pre, 0.34, 0.10))
c["SIMSlotRole"] = np.where(c.DualSIM=="No","Only SIM", np.where(secondary,"Secondary","Primary"))

# network (area level + noise)
circle_q = {k: rng.normal(0,0.6) for k in cn}
netq = np.array([circle_q[x] for x in c.Circle]) - 0.9*rural + 0.3*metro + rng.normal(0,0.6,N)   # higher = better
c["Our5GCoverage"] = np.where(rng.random(N) < sig(0.8 + 1.2*netq - 1.5*rural), "Yes","No")
c["AvgDownloadMbps"] = np.round(np.clip(np.exp(2.7 + 0.35*netq + 0.9*(c.Our5GCoverage=="Yes")*(c.Is5GDevice=="Yes") + rng.normal(0,0.35,N)), 1, 400),1)
c["IndoorCoverageScore"] = np.clip(np.round(3.2 + 0.8*netq + rng.normal(0,0.7,N)),1,5).astype(int)
c["TowerOutageHours90d"] = np.round(np.clip(rng.gamma(1.5, 3, N)*np.exp(-0.5*netq),0,200),1)

# competition (circle level)
comp_price = {k: rng.choice([199,209,239,249,299]) for k in cn}
comp5g = {k: rng.random()<0.6 for k in cn}
c["CompetitorCheapestPlanRs"] = c.Circle.map(comp_price)
c["CompetitorNew5GLaunch90d"] = np.where(c.Circle.map(comp5g), "Yes","No")

# consent
c["MarketingConsent"] = np.where(rng.random(N) < 0.82, "Yes","No (DND)")

# hidden drivers
unhappy = rng.normal(0,1,N)            # latent dissatisfaction
price_sens = rng.normal(0,1,N) + 0.4*pre - 0.3*(tier=="Premium")

# ---------------- monthly usage panel ----------------
base_arpu = np.where(post, rng.normal(620,180,N)*c.FamilyPlanMembers.values**0.6, rng.normal(245,70,N))
base_arpu = np.clip(base_arpu, 99, 3500)
base_data = np.clip(rng.gamma(2.2, 7, N) * (1.4 if True else 1) * np.where(age<30,1.5,1) * np.where(secondary,0.35,1), 0.2, 250)
base_voice = np.clip(rng.gamma(2.5, 180, N) * np.where(secondary,0.4,1), 5, 4000)
# trend over last months driven by latent unhappiness & price sensitivity
decline = 0.012*np.clip(unhappy,0,None) + 0.006*np.clip(price_sens,0,None) + rng.normal(0,0.01,N)
rows = []
m_idx = np.arange(12)
active_from = np.maximum(0, 12 - ten)              # months before activation are absent
for k, per in enumerate(MONTHS):
    alive = k >= active_from
    f = np.exp(-decline*np.maximum(0, k-6)*1.6) * (1 + rng.normal(0,0.07,N))
    arpu = np.round(base_arpu*f*(1 + 0.03*(k>=9)*pre), 0)           # small tariff hike in Jan-26 for prepaid
    data = np.round(base_data*f*(1+0.02*k)*(1+rng.normal(0,0.1,N)),2)
    voice = np.round(base_voice*f*(1+rng.normal(0,0.08,N)))
    rec_cnt = np.where(pre, rng.poisson(np.clip(1.1*f,0.05,None)), np.nan)
    rec_amt = np.where(pre, np.round(arpu*np.where(rec_cnt>0,1,0)), np.nan)
    days_active = np.clip(np.round(30*np.clip(f,0,1) - rng.poisson(1+2*np.clip(unhappy,0,None)*(k>=9))),0,31)
    dcr = np.round(np.clip(rng.gamma(2,0.6,N)*np.exp(-0.45*netq),0,20),2)
    logins = rng.poisson(np.clip((4+6*(age<35))*f,0.1,None))
    rows.append(pd.DataFrame({"CustomerID":c.CustomerID,"Month":str(per),"PlanType":c.PlanType,"ARPU_Rs":arpu,
        "DataGB":data,"VoiceMinutes":voice,"Recharges":rec_cnt,"RechargeAmountRs":rec_amt,"ActiveDays":days_active,
        "DroppedCallRatePct":dcr,"AppLogins":logins})[alive])
mu = pd.concat(rows, ignore_index=True)
# data gaps: ~0.5% months missing
mu = mu.drop(mu.sample(frac=0.005, random_state=int(rng.integers(1e9))).index).reset_index(drop=True)

g = mu.groupby("CustomerID")
last3 = mu[mu.Month>="2026-01"].groupby("CustomerID"); prev3 = mu[(mu.Month>="2025-10")&(mu.Month<"2026-01")].groupby("CustomerID")
agg = pd.DataFrame({
 "ARPU3mRs": last3.ARPU_Rs.mean(), "ARPUPrev3mRs": prev3.ARPU_Rs.mean(),
 "Data3mAvgGB": last3.DataGB.mean(), "DataPrev3mAvgGB": prev3.DataGB.mean(),
 "Voice3mAvgMin": last3.VoiceMinutes.mean(), "ActiveDays3mAvg": last3.ActiveDays.mean(),
 "DroppedCallRate3mPct": last3.DroppedCallRatePct.mean(), "AppLogins3m": last3.AppLogins.sum(),
 "Recharges90d": last3.Recharges.sum(min_count=1), "AvgRechargeRs3m": last3.RechargeAmountRs.mean(),
 "AvgRechargeRsPrev3m": prev3.RechargeAmountRs.mean()})
c = c.merge(agg, left_on="CustomerID", right_index=True, how="left")
c["ARPUChangePct"] = np.round(100*(c.ARPU3mRs/c.ARPUPrev3mRs - 1),1)
c["DataUsageChangePct"] = np.round(100*(c.Data3mAvgGB/c.DataPrev3mAvgGB - 1),1)
for col in ["ARPU3mRs","ARPUPrev3mRs","Data3mAvgGB","DataPrev3mAvgGB","Voice3mAvgMin","ActiveDays3mAvg","DroppedCallRate3mPct","AvgRechargeRs3m","AvgRechargeRsPrev3m"]:
    c[col] = c[col].round(1)
c["RechargeDowntrade"] = np.where(pre, np.where(c.AvgRechargeRs3m < 0.85*c.AvgRechargeRsPrev3m, "Yes","No"), "")
dslr = np.where(pre, np.clip(np.round(rng.gamma(1.3, 9, N)*(1+1.5*np.clip(unhappy,0,None))*np.where(secondary,1.8,1)),0,120), np.nan)
c["DaysSinceLastRecharge"] = dslr
validity = np.where(pre, rng.choice([28,56,84,365],N,p=[0.55,0.2,0.2,0.05]), np.nan)
c["PackValidityDays"] = validity
c["LastRechargeRs"] = np.where(pre, np.round(c.AvgRechargeRs3m.fillna(199)*rng.normal(1,0.12,N)), np.nan)
c["ZeroBalanceDays30d"] = np.where(pre, np.clip(np.round(np.maximum(0, dslr - validity + 30) * (rng.random(N)<0.6)),0,30), np.nan)
c["ActiveDiscountPct"] = np.where(rng.random(N)<0.12, rng.choice([5,10,15,20],N), 0)
c["OverageCharges3mRs"] = np.where(post, np.round(np.clip(rng.gamma(0.6, 90, N)*(rng.random(N)<0.4),0,None)), np.nan)
last_bill = c.ARPU3mRs*np.where(post, 1 + np.clip(rng.gamma(0.8,0.12,N),0,1.2), 1)
c["BillShock"] = np.where(post, np.where(last_bill > 1.3*c.ARPU3mRs, "Yes","No"), "")
dues = np.where(post, np.round(np.where(rng.random(N) < 0.10 + 0.08*np.clip(price_sens,0,None), rng.gamma(1.5,400,N), 0)), np.nan)
c["OutstandingDuesRs"] = dues
c["CostToServeMonthlyRs"] = np.round(np.clip(60 + 0.9*c.Data3mAvgGB.fillna(0) + 0.02*c.Voice3mAvgMin.fillna(0) + rng.normal(0,15,N), 30, None))
c["PriceGapPct"] = np.round(100*(c.ARPU3mRs/c.CompetitorCheapestPlanRs - 1),1)

# ---------------- care interactions log ----------------
rate = np.clip(0.07 + 0.16*np.clip(unhappy,0,None) + 0.09*np.exp(-0.4*netq) + 0.08*post, 0.02, None)  # per month
cats = ["Billing","Network","Recharge failure","Data speed","Plan change","Device/SIM","Porting query"]
care = []
for k, per in enumerate(MONTHS):
    n_ev = rng.poisson(rate)
    n_ev[k < active_from] = 0
    idx = np.repeat(np.arange(N), n_ev)
    if len(idx)==0: continue
    net_w = np.exp(-0.6*netq[idx]); bill_w = np.where(post[idx], 1.6, 0.4)*(1+0.5*np.clip(price_sens[idx],0,None))
    w = np.stack([bill_w, 1.2*net_w, np.where(pre[idx],0.9,0.05), 0.9*net_w, np.full(len(idx),0.5), np.full(len(idx),0.35),
                  0.05 + 0.25*(np.clip(unhappy[idx],0,None)>1)*(k>=9)], axis=1)
    w = w/w.sum(1,keepdims=True); cat = np.array([rng.choice(7, p=r) for r in w])
    day = rng.integers(1, per.days_in_month+1, len(idx))
    chan = rng.choice(["Call centre","App/chat","Store","Social media","Email"], len(idx), p=[0.46,0.28,0.16,0.05,0.05])
    esc = rng.random(len(idx)) < 0.06 + 0.08*np.clip(unhappy[idx],0,None)
    res_days = np.round(np.clip(rng.gamma(1.6, 1.5, len(idx)) * np.where(esc, 3, 1), 0.1, 45), 1)
    fcr = (rng.random(len(idx)) < 0.62 - 0.1*np.clip(unhappy[idx],0,None)) & ~esc
    sentiment = np.clip(np.round(rng.normal(0.1 - 0.35*np.clip(unhappy[idx],0,None) - 0.3*esc, 0.35),2), -1, 1)
    care.append(pd.DataFrame({"CustomerID": c.CustomerID.values[idx],
        "ContactDate": [f"{per}-{d:02d}" for d in day], "Category": np.array(cats)[cat], "Channel": chan,
        "Escalated": np.where(esc,"Yes","No"), "FirstContactResolved": np.where(fcr,"Yes","No"),
        "ResolutionDays": res_days, "SentimentScore": sentiment}))
care = pd.concat(care, ignore_index=True).sort_values(["CustomerID","ContactDate"]).reset_index(drop=True)
care.insert(0, "InteractionID", [f"T{i:07d}" for i in rng.permutation(len(care))])
care["RepeatWithin7d"] = "No"
cd = pd.to_datetime(care.ContactDate)
same = (care.CustomerID == care.CustomerID.shift()) & (care.Category == care.Category.shift()) & ((cd - cd.shift()).dt.days <= 7)
care.loc[same, "RepeatWithin7d"] = "Yes"
r90 = care[pd.to_datetime(care.ContactDate) > SNAP - pd.Timedelta(days=90)]
cg = r90.groupby("CustomerID")
cagg = pd.DataFrame({"CareContacts90d": cg.size(),
  "BillingComplaints90d": cg.Category.apply(lambda s:(s=="Billing").sum()),
  "NetworkComplaints90d": cg.Category.apply(lambda s:s.isin(["Network","Data speed"]).sum()),
  "RechargeFailureComplaints90d": cg.Category.apply(lambda s:(s=="Recharge failure").sum()),
  "RepeatComplaints90d": cg.RepeatWithin7d.apply(lambda s:(s=="Yes").sum()),
  "Escalations90d": cg.Escalated.apply(lambda s:(s=="Yes").sum()),
  "FirstContactResolutionRate": cg.FirstContactResolved.apply(lambda s: round((s=="Yes").mean(),2)),
  "AvgResolutionDays90d": cg.ResolutionDays.mean().round(1),
  "AvgCareSentiment90d": cg.SentimentScore.mean().round(2),
  "PreferredCareChannel": cg.Channel.agg(lambda s: s.value_counts().index[0])})
c = c.merge(cagg, left_on="CustomerID", right_index=True, how="left")
for col in ["CareContacts90d","BillingComplaints90d","NetworkComplaints90d","RechargeFailureComplaints90d","RepeatComplaints90d","Escalations90d"]:
    c[col] = c[col].fillna(0).astype(int)
nps = np.clip(np.round(rng.normal(7.3 - 1.2*np.clip(unhappy,0,None) - 0.3*c.NetworkComplaints90d - 0.25*c.BillingComplaints90d + 0.3*netq, 1.7)),0,10)
c["NPS"] = np.where(rng.random(N) < 0.4, np.nan, nps)

# ---------------- risk before Q1-26 campaign ----------------
yes = lambda s: (np.asarray(s)=="Yes").astype(float)
cte = np.nan_to_num(days_to_end, nan=999)
z0 = (-3.05
  + 0.45*pre + 1.1*secondary - 0.35*(c.SIMSlotRole=="Only SIM")
  - 0.012*np.minimum(ten,60)
  + np.where(cte<=60, 1.3, np.where(cte<=120, 0.5, 0)) - 0.6*((lock>0)&(cte>120))
  + np.where(pre, 0.035*np.nan_to_num(dslr), 0) + 0.45*yes(c.RechargeDowntrade) + 0.03*np.nan_to_num(c.ZeroBalanceDays30d)
  - 0.012*np.clip(c.ARPUChangePct.fillna(0),-60,30) - 0.008*np.clip(c.DataUsageChangePct.fillna(0),-80,50)
  - 0.20*np.clip(c.ActiveDays3mAvg.fillna(30)-25,-25,5)*0.3
  + 0.45*c.NetworkComplaints90d + 0.35*c.BillingComplaints90d + 0.35*c.RechargeFailureComplaints90d
  + 0.35*c.Escalations90d + 0.25*c.RepeatComplaints90d
  - 0.25*(c.IndoorCoverageScore-3) + 0.012*c.TowerOutageHours90d
  + 0.7*((c.Is5GDevice=="Yes")&(c.Our5GCoverage=="No")&(c.CompetitorNew5GLaunch90d=="Yes"))
  + 0.006*np.clip(c.PriceGapPct.fillna(0),-50,200)*np.clip(1+price_sens,0,None)*0.6
  + 0.5*yes(c.BillShock) + 0.0006*np.nan_to_num(dues)
  - 0.45*yes(c.ConvergedBundle) - 0.15*(c.FamilyPlanMembers-1) - 0.2*yes(c.HomeFiber)
  - 0.02*np.clip(c.AppLogins3m,0,40)
  + 0.25*(c.AcquisitionChannel=="MNP port-in")
  + 0.45*np.clip(unhappy,0,None) + rng.normal(0,0.55,N)).values

# ---------------- offer history (3 campaigns) ----------------
offers = {
 "10% loyalty discount (3 mo)":  (lambda a: 0.30*a, 0.24),
 "Free 10GB data add-on":         (lambda a: 49+0*a, 0.20),
 "Lock-in renewal: 1 month free": (lambda a: 1.0*a, 0.14),
 "Free OTT pack (6 mo)":          (lambda a: 149+0*a, 0.16),
 "Priority care (6 mo)":          (lambda a: 30+0*a, 0.10),
 "5G handset EMI cashback":       (lambda a: 1500+0*a, 0.08),
 "Double validity on next recharge": (lambda a: 0.5*a, 0.08)}
names = list(offers)
arpu = c.ARPU3mRs.fillna(c.ARPUPrev3mRs).fillna(250).values
heavy = np.nan_to_num(c.Data3mAvgGB.values) > np.nanpercentile(c.Data3mAvgGB, 60)
many_care = (c.CareContacts90d.values >= 1)
consent = (c.MarketingConsent=="Yes").values
def relevance(k, m):
    if k.startswith("10%"): return 0.4 + 0.6*(np.clip(price_sens[m],0,None)>0.5)
    if "data" in k: return 0.2 + 0.8*heavy[m]
    if "Lock-in" in k: return 0.1 + 0.8*(post[m] & (cte[m]<=120))
    if "OTT" in k: return 0.3 + 0.5*(age[m]<35)
    if "Priority" in k: return 0.2 + 0.7*many_care[m]
    if "5G" in k: return 0.1 + 0.6*((c.Is5GDevice.values[m]=="No") & (tier[m]!="Budget"))
    return 0.2 + 0.7*pre[m]
def effect(k, m):
    if k.startswith("10%"): return -0.6 - 0.8*(np.clip(price_sens[m],0,None)>0.5)
    if "data" in k: return -0.2 - 1.1*heavy[m]
    if "Lock-in" in k: return -0.4 - 1.4*(post[m] & (cte[m]<=120))
    if "OTT" in k: return -0.15 - 0.9*(age[m]<35)
    if "Priority" in k: return -0.2 - 1.1*many_care[m]
    if "5G" in k: return -0.05 + 0*age[m]
    return -0.3 - 0.8*pre[m]
camp_rows = []; eff = np.zeros(N); q1_group = np.full(N, "Not targeted", dtype=object)
q1 = {}
for cname, start, end, reach, is_main in [("Q3-FY26 Retention", "2025-07-07","2025-08-29", 0.10, False),
                                          ("Q4-FY26 Retention", "2025-10-06","2025-11-28", 0.12, False),
                                          ("Q1-CY26 Retention", "2026-01-05","2026-03-06", None, True)]:
    crm = sig(z0 + rng.normal(0,0.9,N))
    tgt = consent & (rng.random(N) < (np.clip(0.06+0.70*crm,0,0.9) if is_main else reach*(0.5+crm)))
    tgt &= (np.arange(N)>=0)
    hold = tgt & (rng.random(N) < (0.25 if is_main else 0.10))
    sent = tgt & ~hold
    offer = np.full(N, "", dtype=object); offer[sent] = rng.choice(names, sent.sum(), p=np.array([offers[k][1] for k in names])/sum(offers[k][1] for k in names))
    rel = np.zeros(N)
    for k in names:
        m = offer==k
        if m.any(): rel[m] = relevance(k, m)
    chan = np.where(sent, rng.choice(["SMS","App push","Outbound call","WhatsApp","Email"],N,p=[0.34,0.22,0.16,0.20,0.08]), "")
    cb = pd.Series(chan).map({"SMS":0,"App push":0.3,"Outbound call":0.6,"WhatsApp":0.4,"Email":-0.3,"":0}).values
    fatigue = np.zeros(N) if not camp_rows else pd.concat(camp_rows).query("Status!='Holdout'").groupby("CustomerID").size().reindex(c.CustomerID).fillna(0).values
    click = sent & (rng.random(N) < sig(-0.7 + 2.1*rel + cb - 0.35*fatigue + rng.normal(0,0.5,N)))
    acc = click & (rng.random(N) < sig(-0.3 + 1.8*rel + 0.3*cb + rng.normal(0,0.5,N)))
    sd = pd.Timestamp(start) + pd.to_timedelta(rng.integers(0,(pd.Timestamp(end)-pd.Timestamp(start)).days+1,N), unit="D")
    red = sd + pd.to_timedelta(rng.integers(0,10,N), unit="D")
    cost = np.zeros(N)
    for k in names:
        m = acc & (offer==k); cost[m] = offers[k][0](arpu[m])
    if is_main:
        for k in names:
            m = acc & (offer==k)
            if m.any(): eff[m] = effect(k, m) - (0.0 if "5G" in k else 0.35) + rng.normal(0,0.25,m.sum())
        q1_group = np.where(sent,"Offer sent",np.where(hold,"Holdout (no offer)","Not targeted"))
        q1 = dict(offer=offer, chan=chan, sd=sd, click=click, acc=acc, red=red, cost=cost, tgt=tgt, sent=sent)
    m = tgt
    camp_rows.append(pd.DataFrame({"CustomerID":c.CustomerID.values[m], "Campaign":cname,
        "Status": np.where(sent[m],"Offer sent","Holdout"), "Offer": offer[m], "Channel": chan[m],
        "SentDate": np.where(sent[m], sd[m].strftime("%Y-%m-%d"), sd[m].strftime("%Y-%m-%d")),
        "ExpiryDate": np.where(sent[m], (sd[m]+pd.Timedelta(days=21)).strftime("%Y-%m-%d"), ""),
        "Clicked": np.where(sent[m], np.where(click[m],"Yes","No"), ""),
        "Accepted": np.where(sent[m], np.where(acc[m],"Yes","No"), ""),
        "RedemptionDate": np.where(acc[m], red[m].strftime("%Y-%m-%d"), ""),
        "OfferCostRs": np.where(sent[m], np.round(cost[m]), np.nan)}))
oh = pd.concat(camp_rows, ignore_index=True)
oh.insert(0, "OfferRecordID", [f"O{i:06d}" for i in range(len(oh))])

# ---------------- churn outcome ----------------
z = z0 + eff
churn = rng.random(N) < sig(z)
c["OffersReceived12m"] = oh[oh.Status=="Offer sent"].groupby("CustomerID").size().reindex(c.CustomerID).fillna(0).astype(int).values
c["Q1CampaignGroup"] = q1_group
c["Q1Offer"] = q1["offer"]; c["Q1OfferChannel"] = q1["chan"]
c["Q1OfferDate"] = np.where(q1["tgt"], q1["sd"].strftime("%Y-%m-%d"), "")
c["Q1OfferClicked"] = np.where(q1["sent"], np.where(q1["click"],"Yes","No"), "")
c["Q1OfferAccepted"] = np.where(q1["sent"], np.where(q1["acc"],"Yes","No"), "")
c["Q1RedemptionDate"] = np.where(q1["acc"], q1["red"].strftime("%Y-%m-%d"), "")
c["Q1OfferCostRs"] = np.where(q1["sent"], np.round(q1["cost"]), np.nan)
c["EstimatedCLVRs"] = np.round(np.clip((arpu - c.CostToServeMonthlyRs.values)*12/np.clip(sig(z0)*4,0.08,None), 0, None), -1)
c["Churn"] = np.where(churn, "Yes","No")
c["ChurnDefinition"] = np.where(pre, "Prepaid: no recharge for 90 days after pack expiry, or port-out", "Postpaid: disconnection or port-out")

# ---- post-churn columns (known only after churn: NOT model features) ----
days = rng.integers(1, 91, N)
c["ChurnDate"] = np.where(churn, (SNAP + pd.to_timedelta(days, unit="D")).strftime("%Y-%m-%d"), "")
invol = churn & post & (np.nan_to_num(dues) > 400) & (rng.random(N)<0.85)
silent = churn & pre & ~invol & (rng.random(N) < sig(-1.4 + 0.035*np.nan_to_num(dslr) + 0.9*secondary))
port = churn & ~invol & ~silent & (rng.random(N) < 0.75)
c["ChurnType"] = np.select([invol, silent, port, churn], ["Involuntary (non-payment)","Silent (stopped recharging)","Voluntary (port-out)","Voluntary (disconnection)"], "")
# reason sampled from each customer's strongest drivers
drv = np.stack([
  0.6 + 0.02*np.clip(c.PriceGapPct.fillna(0),0,200) + 0.8*yes(c.BillShock) + 0.5*np.clip(price_sens,0,None),    # Price
  0.4 + 0.5*c.NetworkComplaints90d - 0.4*(c.IndoorCoverageScore-3) + 0.02*c.TowerOutageHours90d,                  # Network
  0.3 + 1.5*((c.Is5GDevice=="Yes")&(c.Our5GCoverage=="No")&(c.CompetitorNew5GLaunch90d=="Yes")) + 0.4*yes(c.CompetitorNew5GLaunch90d),  # Competitor offer / 5G
  0.3 + 0.5*c.BillingComplaints90d + 0.6*c.Escalations90d + 0.4*c.RepeatComplaints90d,                           # Service & care
  0.25 + 0*age,                                                                                                  # Relocation
  0.2 + 1.2*secondary], axis=1)                                                                                  # Using other SIM
drv = np.clip(drv, 0.05, None); drv = drv/drv.sum(1, keepdims=True)
rs = np.array(["Price / value","Network quality","Competitor offer / 5G","Service & care","Relocation","Using another SIM"])
reason = np.array([rs[rng.choice(6, p=p)] for p in drv])
reason = np.where(invol, "Non-payment", reason)
c["ChurnReason"] = np.where(churn, reason, "")
c["PortOutTo"] = np.where(port, rng.choice(["Competitor A","Competitor B","Competitor C"], N, p=[0.52,0.33,0.15]), "")
c["PortOutRequestDate"] = np.where(port, (pd.to_datetime(pd.Series(c.ChurnDate).replace("",None)) - pd.to_timedelta(rng.integers(3,8,N), unit="D")).dt.strftime("%Y-%m-%d").fillna(""), "")
win = churn & (rng.random(N) < 0.08)
c["ReactivatedWithin60d"] = np.where(churn, np.where(win,"Yes","No"), "")
c["SnapshotDate"] = SNAP.strftime("%Y-%m-%d")

# ---------------- light real-world messiness ----------------
def mess(col, frac, fn):
    i = rng.choice(N, int(frac*N), replace=False); c.loc[i, col] = c.loc[i, col].map(fn)
mess("Circle", 0.004, lambda s: s.upper()); mess("HandsetTier", 0.003, lambda s: " "+s+" ")
c.loc[rng.choice(N, 40, replace=False), "AvgDownloadMbps"] = np.nan
c.loc[rng.choice(N, 6, replace=False), "Voice3mAvgMin"] *= -1
c = pd.concat([c, c.sample(12, random_state=int(rng.integers(1e9)))]).sample(frac=1, random_state=int(rng.integers(1e9))).reset_index(drop=True)

order = ["CustomerID","SnapshotDate","Circle","Zone","Pincode","UrbanRural","Gender","Age","PlanType","AcquisitionChannel",
 "ActivationDate","TenureMonths","LockInMonths","ContractEndDate","DaysToContractEnd","FamilyPlanMembers","HomeFiber","DTH","ConvergedBundle",
 "HandsetTier","DeviceAgeMonths","Is5GDevice","DualSIM","SIMSlotRole","Our5GCoverage","AvgDownloadMbps","IndoorCoverageScore","TowerOutageHours90d",
 "ARPU3mRs","ARPUPrev3mRs","ARPUChangePct","Data3mAvgGB","DataPrev3mAvgGB","DataUsageChangePct","Voice3mAvgMin","ActiveDays3mAvg",
 "DroppedCallRate3mPct","AppLogins3m","DaysSinceLastRecharge","LastRechargeRs","PackValidityDays","Recharges90d","AvgRechargeRs3m",
 "AvgRechargeRsPrev3m","RechargeDowntrade","ZeroBalanceDays30d","ActiveDiscountPct","OverageCharges3mRs","BillShock","OutstandingDuesRs",
 "CostToServeMonthlyRs","EstimatedCLVRs","CompetitorCheapestPlanRs","PriceGapPct","CompetitorNew5GLaunch90d",
 "CareContacts90d","BillingComplaints90d","NetworkComplaints90d","RechargeFailureComplaints90d","RepeatComplaints90d","Escalations90d",
 "FirstContactResolutionRate","AvgResolutionDays90d","AvgCareSentiment90d","PreferredCareChannel","NPS",
 "MarketingConsent","OffersReceived12m","Q1CampaignGroup","Q1Offer","Q1OfferChannel","Q1OfferDate","Q1OfferClicked","Q1OfferAccepted",
 "Q1RedemptionDate","Q1OfferCostRs","Churn","ChurnDefinition","ChurnDate","ChurnType","ChurnReason","PortOutTo","PortOutRequestDate","ReactivatedWithin60d"]
assert set(order)==set(c.columns), set(c.columns)^set(order)
c[order].to_csv(f"{OUT}/customers.csv", index=False)
mu.to_csv(f"{OUT}/monthly_usage.csv", index=False)
care.to_csv(f"{OUT}/care_interactions.csv", index=False)
oh.to_csv(f"{OUT}/offer_history.csv", index=False)
print("seed", SEED, "| customers", len(c), "| monthly rows", len(mu), "| care rows", len(care), "| offer rows", len(oh))
