# ChurnLens live run: Telco sample

- Runtime: 131.3 s (includes the schema proposal)
- Schema proposal source: ai+rules
- Models: pro tier = gemini-3.1-flash-lite, fast tier = gemini-3.1-flash-lite
- Model: Logistic regression, test ROC-AUC 0.831
- Validator: 11/15 items passed, 4 dropped, retries {'insight_agent': 2, 'recommendation_agent': 2}
- Cost: ESTIMATE 0 (Gemini free tier)

## LLM calls per agent

| Agent | Calls | Attempts | OK | Input tokens | Output tokens | Latency (s) |
| --- | --- | --- | --- | --- | --- | --- |
| schema_agent | 1 | 1 | 1 | 4,002 | 1,240 | 6.8 |
| insight_agent | 3 | 6 | 3 | 45,816 | 6,595 | 73.1 |
| recommendation_agent | 3 | 4 | 3 | 50,704 | 5,035 | 41.9 |

## Errors

- none

## Validator details

- insight_agent I1: ok
- insight_agent I2: ok
- insight_agent I3: ok
- insight_agent I4: ok
- insight_agent I5: ok
- insight_agent I6: number 90 in the text is not a declared figure
- insight_agent I7: ok
- insight_agent I8: number 30 in the text is not a declared figure
- insight_agent I9: ok
- insight_agent I10: number 3 in the text is not a declared figure
- recommendation_agent R1: ok
- recommendation_agent R2: impact is for group 'Contract=Month-to-month' but customers_affected is for 'segment_2'; use the impact of the targeted group
- recommendation_agent R3: ok
- recommendation_agent R4: ok
- recommendation_agent R5: ok

## Final insights

I1. **Contract type is the strongest predictor of churn**: Month-to-month contracts have a significantly higher churn rate of 39.81% compared to the overall average of 25.66%. This factor is the top driver of churn in our model (mean |SHAP| = 0.9704).
I2. **High-risk segment identified by network issues**: A specific segment of 1022 customers characterized by high dropped call rates and high network complaints exhibits a churn rate of 38.55%, which is 1.503 times the overall churn rate.
I3. **Tenure is a major churn driver**: Tenure is the second most important driver of churn (mean |SHAP| = 0.7348), with a statistically significant relationship (p < 0.001).
I4. **Fiber optic service associated with higher churn**: Customers with Fiber optic internet service churn at a rate of 35.5%, which is higher than the overall average of 25.66%.
I5. **Lack of online security services linked to churn**: Customers without online security services have a churn rate of 31.12%, compared to 26.53% for those who have it.
I7. **Campaign groups show varying churn rates**: Customers in the holdout group (no offer) have a churn rate of 44.27%, while those who were sent an offer have a churn rate of 37.63%.
I9. **Demographic factors show no significant impact**: Factors such as SeniorCitizen status (p = 0.1001) and CityTier (p = 0.2901) do not show a statistically significant association with churn.

## Final recommendations

R1 (priority 1, medium_term, medium effort): **Launch a loyalty campaign offering incentives for month-to-month customers to switch to annual contracts.** Problem: Month-to-month contract customers churn at 39.81%, significantly higher than the overall average of 25.66%. Target: Month-to-month contract customers. Impact: 153.7 (If churn in this group fell by 10% (relative), with everything else unchanged. Based on observed churn; not a causal estimate.)
R3 (priority 3, medium_term, medium effort): **Review the fiber optic service experience and introduce value-added bundles to improve retention.** Problem: Fiber optic internet service customers churn at a rate of 35.5%. Target: Fiber optic internet customers. Impact: 111.9 (If churn in this group fell by 10% (relative), with everything else unchanged. Based on observed churn; not a causal estimate.)
R4 (priority 4, quick_win, low effort): **Promote online security add-ons to customers currently not subscribed to these services.** Problem: Customers without online security services have a higher churn rate of 31.12%. Target: Customers without online security. Impact: 107.9 (If churn in this group fell by 10% (relative), with everything else unchanged. Based on observed churn; not a causal estimate.)
R5 (priority 5, quick_win, low effort): **Offer a trial period for tech support services to customers who currently lack this feature.** Problem: Customers without tech support services churn at 31.12%. Target: Customers without tech support. Impact: 106.7 (If churn in this group fell by 10% (relative), with everything else unchanged. Based on observed churn; not a causal estimate.)
